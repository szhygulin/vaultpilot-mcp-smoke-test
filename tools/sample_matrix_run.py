#!/usr/bin/env python3
"""
tools/sample_matrix_run.py — Partition (expert + newcomer) matrix cells into
fixed-size batches, then track per-batch run progress. The user decides how
many batches to dispatch per session / week / day; the tool just hands them
the next pending batch and counts overall progress.

Why this exists:
  A full matrix run on both audiences is 1110 cells ≈ ~56M tokens, well over
  any single 5-hour Anthropic session and into the weekly Sonnet bucket too.
  Splitting into batches sized to fill ~50% of one 5-hour all-models session
  lets you dispatch 1-2 batches per session, paced however suits you.

Sampling strategy:
  - Flatten 1110 cells (450 expert + 660 newcomer, each × {A, B, C}).
  - Shuffle once with a fixed seed (default 42) — deterministic, reproducible.
  - Slice into batches of N cells, where
        N = floor(SESSION_ALL_MODELS × BATCH_SESSION_FRACTION / TOKENS_PER_CELL)
    Defaults: 5M × 0.5 / 50k = 50 cells/batch → 23 batches total for 1110 cells.
  - Each batch is non-overlapping; cumulatively they cover every cell exactly once.

Subcommands:
  init                   Create partition.json + progress.json (one-time).
  next-batch             Print the next pending batch's cells and write its
                         scripts.json under runs/matrix-sampled/batch-NN/.
                         Marks the batch as in_progress.
  mark-completed --batch N [--transcripts PATH]
                         Mark batch N as completed.
  status                 Show overall progress (X / total batches done).

Outputs (under runs/matrix-sampled/):
  partition.json         Immutable plan — never edit by hand.
  progress.json          Per-batch status: pending | in_progress | completed.
  batch-NN/scripts.json  The cells dispatched in batch N, in the format
                         expected by the skill's Phase 3 dispatch.
"""
import argparse
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERT_PATH = f'{REPO}/test-vectors/expert-matrix.json'
NEWCOMER_PATH = f'{REPO}/test-vectors/newcomer-matrix.json'
SAMPLE_DIR = f'{REPO}/runs/matrix-sampled'
PARTITION_PATH = f'{SAMPLE_DIR}/partition.json'
PROGRESS_PATH = f'{SAMPLE_DIR}/progress.json'

# Defaults align with skill/SKILL.md Phase 2.5 anchors.
DEFAULT_SONNET_WEEKLY = 30_000_000
DEFAULT_ALL_MODELS_WEEKLY = 50_000_000
DEFAULT_SESSION_ALL_MODELS = 5_000_000  # 5-hour all-models cap, override via flag
DEFAULT_TOKENS_PER_CELL = 50_000
DEFAULT_BATCH_SESSION_FRACTION = 0.5  # batch fills this much of one 5-hour session
DEFAULT_SEED = 42


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _load_matrix_cells(path: str, label: str) -> list[dict]:
    matrix = json.load(open(path))
    cells = []
    for row in matrix['rows']:
        for role in ('A', 'B', 'C'):
            cells.append({
                'matrix': label,
                'row_id': row['id'],
                'role': role,
            })
    return cells


def _flatten_all() -> list[dict]:
    return _load_matrix_cells(EXPERT_PATH, 'expert') + \
           _load_matrix_cells(NEWCOMER_PATH, 'newcomer')


def cmd_init(args: argparse.Namespace) -> None:
    if os.path.exists(PARTITION_PATH) and not args.force:
        sys.exit(f"{PARTITION_PATH} already exists. Use --force to reshuffle.")

    cells = _flatten_all()
    rnd = random.Random(args.seed)
    rnd.shuffle(cells)

    if args.batch_size is None:
        batch_size = max(1, int(args.session_all_models *
                                DEFAULT_BATCH_SESSION_FRACTION /
                                args.per_cell))
    else:
        batch_size = args.batch_size

    batches = [cells[i:i + batch_size]
               for i in range(0, len(cells), batch_size)]

    os.makedirs(SAMPLE_DIR, exist_ok=True)

    partition = {
        'created_at': _now(),
        'seed': args.seed,
        'batch_size': batch_size,
        'budget_constraint': {
            'sonnet_weekly_tokens': args.sonnet_weekly,
            'all_models_weekly_tokens': args.all_models_weekly,
            'session_all_models_tokens': args.session_all_models,
            'tokens_per_cell': args.per_cell,
            'batch_session_fraction': DEFAULT_BATCH_SESSION_FRACTION,
        },
        'total_cells': len(cells),
        'total_batches': len(batches),
        'batches': [
            {'batch': i + 1, 'cells': b}
            for i, b in enumerate(batches)
        ],
    }
    with open(PARTITION_PATH, 'w') as f:
        json.dump(partition, f, indent=2)

    progress = {
        'created_at': partition['created_at'],
        'total_batches': len(batches),
        'batches': [
            {
                'batch': i + 1,
                'cell_count': len(b),
                'status': 'pending',
                'started_at': None,
                'completed_at': None,
                'transcripts_dir': None,
            }
            for i, b in enumerate(batches)
        ],
    }
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2)

    per_batch_tokens = batch_size * args.per_cell
    pct_batch_sonnet = per_batch_tokens / args.sonnet_weekly * 100
    pct_batch_all = per_batch_tokens / args.all_models_weekly * 100
    pct_batch_session = per_batch_tokens / args.session_all_models * 100

    print(f"wrote {PARTITION_PATH}")
    print(f"  total cells:     {partition['total_cells']}")
    print(f"  batch size:      {batch_size} cells = ~{per_batch_tokens / 1e6:.2f}M tokens")
    print(f"  total batches:   {partition['total_batches']}")
    print()
    print(f"Per batch vs Max-20x caps:")
    print(f"  Sonnet weekly:       ~{pct_batch_sonnet:.1f}% of bucket "
          f"(anchor ~{args.sonnet_weekly / 1e6:.0f}M)")
    print(f"  All-models weekly:   ~{pct_batch_all:.1f}% of bucket "
          f"(anchor ~{args.all_models_weekly / 1e6:.0f}M)")
    print(f"  All-models session:  ~{pct_batch_session:.1f}% of bucket "
          f"(anchor ~{args.session_all_models / 1e6:.0f}M)")
    print(f"  seed: {partition['seed']}")


def cmd_next_batch(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    partition = json.load(open(PARTITION_PATH))

    pending = [b for b in progress['batches'] if b['status'] == 'pending']
    if not pending:
        in_prog = [b for b in progress['batches'] if b['status'] == 'in_progress']
        if in_prog:
            print(f"batch {in_prog[0]['batch']} already in_progress — "
                  f"finish it (mark-completed) before starting next.")
        else:
            print("All batches completed.")
        return

    batch_n = pending[0]['batch']
    batch_cells = next(b['cells'] for b in partition['batches']
                       if b['batch'] == batch_n)

    expert = json.load(open(EXPERT_PATH))
    newcomer = json.load(open(NEWCOMER_PATH))
    expert_by_id = {r['id']: r for r in expert['rows']}
    newcomer_by_id = {r['id']: r for r in newcomer['rows']}

    hydrated = []
    for c in batch_cells:
        row = (expert_by_id if c['matrix'] == 'expert'
               else newcomer_by_id)[c['row_id']]
        hydrated.append({
            'id': f"{c['matrix']}-{c['row_id']}-{c['role']}",
            'matrix': c['matrix'],
            'row_id': c['row_id'],
            'role': c['role'],
            'category': row['category'],
            'chain': row.get('chain'),
            'script': row['script'],
            'attack': row['cells'][c['role']],
        })

    batch_dir = f'{SAMPLE_DIR}/batch-{batch_n:02d}'
    os.makedirs(batch_dir, exist_ok=True)
    scripts_path = f'{batch_dir}/scripts.json'

    out = {
        '_comment': (
            f'Batch {batch_n} of {progress["total_batches"]} — '
            f'{len(hydrated)} cells. Dispatch all of them concurrently '
            'via skill/SKILL.md Phase 3.'
        ),
        'batch': batch_n,
        'addressBook': expert.get('addressBook', {}),
        'roleLegend': expert.get('roleLegend', {}),
        'scripts': hydrated,
    }
    with open(scripts_path, 'w') as f:
        json.dump(out, f, indent=2)

    pending[0]['status'] = 'in_progress'
    pending[0]['started_at'] = _now()
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2)

    matrix_counts = {'expert': 0, 'newcomer': 0}
    role_counts = {'A': 0, 'B': 0, 'C': 0}
    for c in hydrated:
        matrix_counts[c['matrix']] += 1
        role_counts[c['role']] += 1

    bc = partition['budget_constraint']
    per_cell = bc['tokens_per_cell']
    sonnet_weekly = bc['sonnet_weekly_tokens']
    all_models_weekly = bc.get('all_models_weekly_tokens', DEFAULT_ALL_MODELS_WEEKLY)
    session_all_models = bc.get('session_all_models_tokens', DEFAULT_SESSION_ALL_MODELS)

    per_batch_tokens = len(hydrated) * per_cell
    pct_batch_sonnet = per_batch_tokens / sonnet_weekly * 100
    pct_batch_all = per_batch_tokens / all_models_weekly * 100
    pct_batch_session = per_batch_tokens / session_all_models * 100

    total_batches = progress['total_batches']
    batches_done = sum(1 for b in progress['batches']
                       if b['status'] == 'completed')

    print(f"wrote {scripts_path}")
    print()
    print(f"=== Phase 2.5 cost preflight (batch {batch_n}) ===")
    print(f"Sample:   {len(hydrated)} cells "
          f"(expert: {matrix_counts['expert']}, newcomer: {matrix_counts['newcomer']}; "
          f"A: {role_counts['A']}, B: {role_counts['B']}, C: {role_counts['C']})")
    print(f"Tokens:   ~{per_batch_tokens / 1e6:.2f}M for this batch")
    print(f"Progress: {batches_done} / {total_batches} batches done")
    print()
    print(f"Per batch vs Max-20x caps:")
    print(f"  Sonnet weekly:       ~{pct_batch_sonnet:.1f}% of bucket "
          f"(anchor ~{sonnet_weekly / 1e6:.0f}M)")
    print(f"  All-models weekly:   ~{pct_batch_all:.1f}% of bucket "
          f"(anchor ~{all_models_weekly / 1e6:.0f}M)")
    print(f"  All-models session:  ~{pct_batch_session:.1f}% of bucket "
          f"(anchor ~{session_all_models / 1e6:.0f}M)")
    print()
    print(f"Rough estimates — verify on your account dashboard. Override "
          f"anchors via `init --sonnet-weekly`, `--all-models-weekly`, "
          f"`--session-all-models`.")
    print()
    print(f"Next: orchestrator confirms with user, then dispatch Phase 3 "
          f"over {scripts_path}, then `mark-completed --batch {batch_n}`.")


def cmd_mark_completed(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    batch = next((b for b in progress['batches']
                  if b['batch'] == args.batch), None)
    if not batch:
        sys.exit(f"Batch {args.batch} not in partition (have batches "
                 f"1..{progress['total_batches']}).")
    batch['status'] = 'completed'
    batch['completed_at'] = _now()
    if args.transcripts:
        batch['transcripts_dir'] = args.transcripts
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2)
    print(f"batch {args.batch} marked completed at {batch['completed_at']}")


def cmd_status(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    counts = {'completed': 0, 'in_progress': 0, 'pending': 0}
    for b in progress['batches']:
        counts[b['status']] += 1
    total = progress['total_batches']
    print(f"batches: {counts['completed']} / {total} done  "
          f"(in_progress={counts['in_progress']}  pending={counts['pending']})")
    if args.verbose:
        for b in progress['batches']:
            marker = {'completed': '[X]', 'in_progress': '[.]', 'pending': '[ ]'}[b['status']]
            started = b.get('started_at') or '—'
            completed = b.get('completed_at') or '—'
            print(f"  {marker} batch {b['batch']:02d}  {b['cell_count']:>3} cells  "
                  f"{b['status']:12s}  started={started}  completed={completed}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_init = sub.add_parser('init', help='Create the partition (one-time).')
    p_init.add_argument('--seed', type=int, default=DEFAULT_SEED)
    p_init.add_argument('--sonnet-weekly', dest='sonnet_weekly',
                        type=int, default=DEFAULT_SONNET_WEEKLY,
                        help='Sonnet weekly budget in tokens (default: 30M)')
    p_init.add_argument('--all-models-weekly', dest='all_models_weekly',
                        type=int, default=DEFAULT_ALL_MODELS_WEEKLY,
                        help='All-models weekly budget in tokens (default: 50M)')
    p_init.add_argument('--session-all-models', dest='session_all_models',
                        type=int, default=DEFAULT_SESSION_ALL_MODELS,
                        help='5-hour all-models cap in tokens (default: 5M; tune to plan)')
    p_init.add_argument('--per-cell', dest='per_cell',
                        type=int, default=DEFAULT_TOKENS_PER_CELL,
                        help='Tokens per cell estimate (default: 50k)')
    p_init.add_argument('--batch-size', dest='batch_size',
                        type=int, default=None,
                        help='Concurrent subagents per batch '
                             '(default: auto-derive to fill ~50%% of session anchor)')
    p_init.add_argument('--force', action='store_true',
                        help='Overwrite existing partition.json + progress.json')
    p_init.set_defaults(func=cmd_init)

    p_next = sub.add_parser('next-batch',
                            help='Print and persist next pending batch.')
    p_next.set_defaults(func=cmd_next_batch)

    p_mark = sub.add_parser('mark-completed', help='Mark a batch as run.')
    p_mark.add_argument('--batch', type=int, required=True)
    p_mark.add_argument('--transcripts', help='Path to transcripts dir.')
    p_mark.set_defaults(func=cmd_mark_completed)

    p_stat = sub.add_parser('status', help='Show progress.')
    p_stat.add_argument('-v', '--verbose', action='store_true',
                        help='Show per-batch detail.')
    p_stat.set_defaults(func=cmd_status)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
