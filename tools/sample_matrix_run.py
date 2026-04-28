#!/usr/bin/env python3
"""
tools/sample_matrix_run.py — Partition (expert + newcomer) matrix cells into
weekly samples that fit a budget; track per-week run progress.

Why this exists:
  A full matrix run on both audiences is 1110 cells ≈ ~56M tokens, which
  exceeds the Max-x20 weekly Sonnet bucket. Splitting across ~3 weeks with
  random partitioning lets every cell run exactly once over time without any
  single week blowing the budget.

Sampling strategy:
  - Flatten 1110 cells (450 expert + 660 newcomer, each × {A, B, C}).
  - Shuffle once with a fixed seed (default 42) — partition is deterministic
    and reproducible from the seed.
  - Split into weekly chunks of N cells, where
        N = floor(SONNET_WEEKLY × FRACTION / TOKENS_PER_CELL)
    Defaults: SONNET_WEEKLY=30M, FRACTION=0.9, TOKENS_PER_CELL=50k → N=540.
  - Weekly chunks are non-overlapping; they cumulatively cover every cell
    exactly once.
  - Per-batch dispatch (within a week's run) uses BATCH_SIZE concurrent
    subagents — bounded by the per-session rate-limit, not the weekly budget.

Subcommands:
  init                   Create partition.json + progress.json (one-time).
  next-week              Print the next pending week's cells and write its
                         scripts.json under runs/matrix-sampled/week-NN/.
                         Marks the week as in_progress.
  mark-completed --week N [--transcripts PATH]
                         Mark week N as completed, optionally record where
                         its transcripts live.
  status                 Show overall progress.

Outputs (under runs/matrix-sampled/):
  partition.json         Immutable plan — never edit by hand. Re-run
                         `init --force` if you really need to reshuffle.
  progress.json          Per-week status: pending | in_progress | completed.
  week-NN/scripts.json   The cells dispatched that week, in the format
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

# Defaults align with skill/SKILL.md Phase 2.5 anchors. Override via flags
# if the user's plan / model behavior changes.
DEFAULT_SONNET_WEEKLY = 30_000_000
DEFAULT_ALL_MODELS_WEEKLY = 50_000_000
DEFAULT_SESSION_ALL_MODELS = 5_000_000  # 5-hour window all-models cap; rough Max-20x estimate, override via flag
DEFAULT_FRACTION = 0.9
DEFAULT_TOKENS_PER_CELL = 50_000
DEFAULT_ANALYSIS_TOKENS = 250_000
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

    cells_per_week = int(args.sonnet_weekly * args.fraction / args.per_cell)
    if cells_per_week < 1:
        sys.exit("derived cells_per_week < 1 — check your budget args")

    # Auto-derive batch size to fill DEFAULT_BATCH_SESSION_FRACTION of one
    # 5-hour all-models session; --batch-size overrides.
    if args.batch_size is None:
        batch_size = max(1, int(args.session_all_models *
                                DEFAULT_BATCH_SESSION_FRACTION /
                                args.per_cell))
    else:
        batch_size = args.batch_size

    weeks = [cells[i:i + cells_per_week]
             for i in range(0, len(cells), cells_per_week)]
    batches_per_week = [(len(w) + batch_size - 1) // batch_size for w in weeks]
    total_batches = sum(batches_per_week)

    os.makedirs(SAMPLE_DIR, exist_ok=True)

    partition = {
        'created_at': _now(),
        'seed': args.seed,
        'cells_per_week': cells_per_week,
        'budget_constraint': {
            'sonnet_weekly_tokens': args.sonnet_weekly,
            'all_models_weekly_tokens': args.all_models_weekly,
            'session_all_models_tokens': args.session_all_models,
            'budget_fraction': args.fraction,
            'tokens_per_cell': args.per_cell,
            'analysis_tokens': args.analysis_tokens,
            'batch_session_fraction': DEFAULT_BATCH_SESSION_FRACTION,
            'derived_cells_per_week': cells_per_week,
        },
        'batch_size': batch_size,
        'total_cells': len(cells),
        'total_weeks': len(weeks),
        'total_batches': total_batches,
        'weeks': [
            {'week': i + 1, 'batches': batches_per_week[i], 'cells': w}
            for i, w in enumerate(weeks)
        ],
    }
    with open(PARTITION_PATH, 'w') as f:
        json.dump(partition, f, indent=2)

    progress = {
        'created_at': partition['created_at'],
        'total_weeks': len(weeks),
        'total_batches': total_batches,
        'weeks': [
            {
                'week': i + 1,
                'cell_count': len(w),
                'batches': batches_per_week[i],
                'status': 'pending',
                'started_at': None,
                'completed_at': None,
                'transcripts_dir': None,
            }
            for i, w in enumerate(weeks)
        ],
    }
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2)

    per_batch_tokens = batch_size * args.per_cell
    pct_batch_sonnet = per_batch_tokens / args.sonnet_weekly * 100
    pct_batch_all = per_batch_tokens / args.all_models_weekly * 100
    pct_batch_session = per_batch_tokens / args.session_all_models * 100

    print(f"wrote {PARTITION_PATH}")
    print(f"  total cells:    {partition['total_cells']}")
    print(f"  cells/week:     {partition['cells_per_week']}")
    print(f"  total weeks:    {partition['total_weeks']}")
    print(f"  batch:          {batch_size} cells = ~{per_batch_tokens / 1e6:.2f}M tokens")
    print(f"  total batches:  {total_batches} "
          f"(per week: {', '.join(str(b) for b in batches_per_week)})")
    print()
    print(f"Per batch vs Max-20x caps:")
    print(f"  Sonnet weekly:       ~{pct_batch_sonnet:.1f}% of bucket "
          f"(anchor ~{args.sonnet_weekly / 1e6:.0f}M)")
    print(f"  All-models weekly:   ~{pct_batch_all:.1f}% of bucket "
          f"(anchor ~{args.all_models_weekly / 1e6:.0f}M)")
    print(f"  All-models session:  ~{pct_batch_session:.1f}% of bucket "
          f"(anchor ~{args.session_all_models / 1e6:.0f}M)")
    print(f"  seed: {partition['seed']}")


def cmd_next_week(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    partition = json.load(open(PARTITION_PATH))

    pending = [w for w in progress['weeks'] if w['status'] == 'pending']
    if not pending:
        in_prog = [w for w in progress['weeks'] if w['status'] == 'in_progress']
        if in_prog:
            print(f"week {in_prog[0]['week']} already in_progress — "
                  f"finish it (mark-completed) before starting next.")
        else:
            print("All weeks completed.")
        return

    week_n = pending[0]['week']
    week_cells = next(w['cells'] for w in partition['weeks']
                      if w['week'] == week_n)

    expert = json.load(open(EXPERT_PATH))
    newcomer = json.load(open(NEWCOMER_PATH))
    expert_by_id = {r['id']: r for r in expert['rows']}
    newcomer_by_id = {r['id']: r for r in newcomer['rows']}

    hydrated = []
    for c in week_cells:
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

    week_dir = f'{SAMPLE_DIR}/week-{week_n:02d}'
    os.makedirs(week_dir, exist_ok=True)
    scripts_path = f'{week_dir}/scripts.json'

    out = {
        '_comment': (
            f'Week {week_n} of {progress["total_weeks"]} — '
            f'{len(hydrated)} cells dispatched in this run. '
            'Schema is the same shape Phase 3 of skill/SKILL.md expects, '
            'with role + attack added per script for the adversarial '
            'subagent prompt template.'
        ),
        'week': week_n,
        'batch_size': partition['batch_size'],
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
    batch_size = partition['batch_size']

    per_batch_tokens = batch_size * per_cell
    pct_batch_sonnet_weekly = per_batch_tokens / sonnet_weekly * 100
    pct_batch_all_weekly = per_batch_tokens / all_models_weekly * 100
    pct_batch_session = per_batch_tokens / session_all_models * 100

    batches_this_week = next(w['batches'] for w in partition['weeks']
                             if w['week'] == week_n)
    total_batches = partition.get(
        'total_batches',
        sum(w.get('batches', 0) for w in partition['weeks'])
    )
    batches_done = sum(
        w.get('batches', 0)
        for w in progress['weeks']
        if w['status'] == 'completed'
    )

    print(f"wrote {scripts_path}")
    print()
    print(f"=== Phase 2.5 cost preflight (week {week_n}) ===")
    print(f"Sample: {len(hydrated)} cells "
          f"(expert: {matrix_counts['expert']}, newcomer: {matrix_counts['newcomer']}; "
          f"A: {role_counts['A']}, B: {role_counts['B']}, C: {role_counts['C']})")
    print(f"Batch:  {batch_size} cells = ~{per_batch_tokens / 1e6:.2f}M tokens")
    print(f"Batches this week: {batches_this_week}  "
          f"|  Plan: {batches_done} / {total_batches} batches done")
    print()
    print(f"Per batch vs Max-20x caps:")
    print(f"  Sonnet weekly:       ~{pct_batch_sonnet_weekly:.1f}% of bucket "
          f"(anchor ~{sonnet_weekly / 1e6:.0f}M)")
    print(f"  All-models weekly:   ~{pct_batch_all_weekly:.1f}% of bucket "
          f"(anchor ~{all_models_weekly / 1e6:.0f}M)")
    print(f"  All-models session:  ~{pct_batch_session:.1f}% of bucket "
          f"(anchor ~{session_all_models / 1e6:.0f}M)")
    print()
    print(f"Rough estimates — verify on your account dashboard. Override "
          f"anchors via `init --sonnet-weekly`, `--all-models-weekly`, "
          f"`--session-all-models`.")
    print()
    print(f"Next: orchestrator confirms with user, then dispatch Phase 3 "
          f"over {scripts_path}, then `mark-completed --week {week_n}`.")


def cmd_mark_completed(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    week = next((w for w in progress['weeks'] if w['week'] == args.week), None)
    if not week:
        sys.exit(f"Week {args.week} not in partition (have weeks 1..{progress['total_weeks']}).")
    week['status'] = 'completed'
    week['completed_at'] = _now()
    if args.transcripts:
        week['transcripts_dir'] = args.transcripts
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2)
    print(f"week {args.week} marked completed at {week['completed_at']}")


def cmd_status(args: argparse.Namespace) -> None:
    if not os.path.exists(PROGRESS_PATH):
        sys.exit("No partition yet. Run `init` first.")
    progress = json.load(open(PROGRESS_PATH))
    counts = {'completed': 0, 'in_progress': 0, 'pending': 0}
    for w in progress['weeks']:
        counts[w['status']] += 1
    print(f"weeks: {progress['total_weeks']}  "
          f"(completed={counts['completed']}  "
          f"in_progress={counts['in_progress']}  "
          f"pending={counts['pending']})")
    for w in progress['weeks']:
        marker = {'completed': '[X]', 'in_progress': '[.]', 'pending': '[ ]'}[w['status']]
        started = w.get('started_at') or '—'
        completed = w.get('completed_at') or '—'
        print(f"  {marker} week {w['week']:02d}  {w['cell_count']:>4} cells  "
              f"{w['status']:12s}  started={started}  completed={completed}")


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
                        help='5-hour-window all-models cap in tokens (default: 5M; tune to actual plan)')
    p_init.add_argument('--analysis-tokens', dest='analysis_tokens',
                        type=int, default=DEFAULT_ANALYSIS_TOKENS,
                        help='Phase 5 analysis subagent token estimate (default: 250k)')
    p_init.add_argument('--fraction', type=float, default=DEFAULT_FRACTION,
                        help='Fraction of weekly budget to use (default: 0.9)')
    p_init.add_argument('--per-cell', dest='per_cell',
                        type=int, default=DEFAULT_TOKENS_PER_CELL,
                        help='Tokens per cell estimate (default: 50k)')
    p_init.add_argument('--batch-size', dest='batch_size',
                        type=int, default=None,
                        help='Concurrent subagents per dispatch batch '
                             '(default: auto-derive to fill ~50%% of session anchor)')
    p_init.add_argument('--force', action='store_true',
                        help='Overwrite existing partition.json + progress.json')
    p_init.set_defaults(func=cmd_init)

    p_next = sub.add_parser('next-week',
                            help='Print and persist next pending week.')
    p_next.set_defaults(func=cmd_next_week)

    p_mark = sub.add_parser('mark-completed', help='Mark a week as run.')
    p_mark.add_argument('--week', type=int, required=True)
    p_mark.add_argument('--transcripts', help='Path to transcripts dir.')
    p_mark.set_defaults(func=cmd_mark_completed)

    p_stat = sub.add_parser('status', help='Show progress.')
    p_stat.set_defaults(func=cmd_status)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
