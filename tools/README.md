# tools/

Helper scripts used during smoke-test runs. These are the little utilities the parent agent shells out to between Claude Code subagent dispatches — extracted from inline usage in the original runs so they're reusable for re-runs.

| Script | Purpose | When |
|---|---|---|
| `concat_transcripts.sh` | Bash loop concatenating `transcripts/*.txt` into a single `all_transcripts.txt` corpus | Phase 4 (between dispatch and analysis) |
| `parse_summary.py` | Python parser extracting `SCRIPT_ID/CATEGORY/CHAIN/OUTCOME/OBSERVATIONS` per transcript → `summary.txt` | Phase 5 step 5.2 (honest mode) |
| `parse_summary_adversarial.py` | Same as above, plus the `[ADVERSARIAL_RESULT]` block (role / attack / defense_layer / did_user_get_tricked) | Phase 5 step 5.2 (adversarial mode) |
| `find_missing_transcripts.sh` | Diff between expected script IDs (from a `scripts.json`) and on-disk `transcripts/*.txt` — surfaces which subagents haven't completed yet | Phase 3 monitoring |
| `wait_for_transcripts.sh` | Block until a target transcript count is reached. Designed for `Bash(run_in_background:true)` so the parent agent gets a single "all done" notification | Phase 3 / 4 transition |
| `sample_matrix_run.py` | Partition the (expert + newcomer) matrix into fixed-size random batches; track per-batch progress so every cell runs exactly once. User decides how many batches to dispatch per session/week. | Phase 2.5 (cost preflight) for matrix-mode runs |

### `sample_matrix_run.py` — usage

A full matrix run on both audiences is 1110 cells ≈ ~56M tokens, well over any single 5-hour Anthropic session and into the weekly Sonnet bucket too. This tool partitions the work into fixed-size batches (default ~50 cells = ~2.5M tokens, sized to fill ~50% of one 5-hour all-models session). Dispatch batches at whatever cadence suits you; the tool tracks total progress.

```bash
# One-time: build the partition + progress files (already done if committed)
python3 tools/sample_matrix_run.py init [--seed N] \
    [--sonnet-weekly 30000000] [--all-models-weekly 50000000] \
    [--session-all-models 5000000] [--per-cell 50000] \
    [--batch-size N]   # auto-derived from session anchor if omitted

# Get the next pending batch, writes runs/matrix-sampled/batch-NN/scripts.json
# AND prints the Phase 2.5 cost preflight report (per-batch % of each cap +
# total progress).
python3 tools/sample_matrix_run.py next-batch

# After dispatching the batch
python3 tools/sample_matrix_run.py mark-completed --batch N \
    [--transcripts runs/matrix-sampled/batch-NN/transcripts]

# Anytime: see overall progress
python3 tools/sample_matrix_run.py status [-v]
```

The `next-batch` output is the Phase 2.5 cost preflight report — surface it to the user verbatim and wait for confirmation before dispatching.

State files (under `runs/matrix-sampled/`):
- `partition.json` — immutable plan; `init --force` to reshuffle from a new seed
- `progress.json` — `pending | in_progress | completed` per batch
- `batch-NN/scripts.json` — the cells dispatched in batch N, in the format the skill's Phase 3 dispatch consumes (one entry per cell, with role + attack inlined)

Default partition: 50 cells/batch × 23 batches = 1110 cells. Override budget anchors via flags if your plan changes; `--batch-size` overrides the auto-derived value if you want a different fill ratio.

## Conventions

- All tools take an optional `<workdir>` argument; default is the current directory.
- All tools assume the standard layout: `<workdir>/transcripts/NNN.txt`, `<workdir>/scripts.json`.
- Tools never modify transcripts — they read and produce derivative files only.

## Why these are scripts, not inline

In production runs Claude Code's parent agent shells out via `Bash` for these steps. Saving them as actual scripts:
1. Keeps the parent agent's context cleaner (one tool call per step instead of inline Python heredocs).
2. Makes the recipe reproducible by humans without Claude Code.
3. Forces the script-vs-prompt boundary — anything ad-hoc enough to write inline probably isn't a recurring step.

## Adding new tools

If a step is repeated across runs (>2 times) and the inline version is non-trivial (>20 LoC, or has a non-obvious regex), extract it here. Keep each tool single-purpose; compose them in shell pipelines rather than building a monolith.
