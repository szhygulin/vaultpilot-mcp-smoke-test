# tools/

Helper scripts used during smoke-test runs. These are the little utilities the parent agent shells out to between Claude Code subagent dispatches — extracted from inline usage in the original runs so they're reusable for re-runs.

| Script | Purpose | When |
|---|---|---|
| `concat_transcripts.sh` | Bash loop concatenating `transcripts/*.txt` into a single `all_transcripts.txt` corpus | Phase 4 (between dispatch and analysis) |
| `parse_summary.py` | Python parser extracting `SCRIPT_ID/CATEGORY/CHAIN/OUTCOME/OBSERVATIONS` per transcript → `summary.txt` | Phase 5 step 5.2 (honest mode) |
| `parse_summary_adversarial.py` | Same as above, plus the `[ADVERSARIAL_RESULT]` block (role / attack / defense_layer / did_user_get_tricked) | Phase 5 step 5.2 (adversarial mode) |
| `find_missing_transcripts.sh` | Diff between expected script IDs (from a `scripts.json`) and on-disk `transcripts/*.txt` — surfaces which subagents haven't completed yet | Phase 3 monitoring |
| `wait_for_transcripts.sh` | Block until a target transcript count is reached. Designed for `Bash(run_in_background:true)` so the parent agent gets a single "all done" notification | Phase 3 / 4 transition |
| `sample_matrix_run.py` | Partition the (expert + newcomer) matrix into weekly random samples that fit the Sonnet-weekly budget; track per-week progress so every cell runs exactly once across N weeks | Phase 2.5 (cost preflight) for matrix-mode runs |

### `sample_matrix_run.py` — usage

A full matrix run on both audiences is 1110 cells ≈ ~56M tokens, which exceeds the Max-x20 weekly Sonnet bucket. This tool partitions the work into non-overlapping weekly samples sized to fit ~90% of the weekly budget, with a fixed seed so the partition is deterministic.

```bash
# One-time: build the partition + progress files (already done if committed)
python3 tools/sample_matrix_run.py init [--seed N] \
    [--sonnet-weekly 30000000] [--fraction 0.9] \
    [--per-cell 50000] [--batch-size 15]

# Each week: get the next pending sample, writes runs/matrix-sampled/week-NN/scripts.json
python3 tools/sample_matrix_run.py next-week

# After dispatching + analyzing the week's run
python3 tools/sample_matrix_run.py mark-completed --week N \
    [--transcripts runs/matrix-sampled/week-NN/transcripts]

# Anytime: see overall progress
python3 tools/sample_matrix_run.py status
```

State files (under `runs/matrix-sampled/`):
- `partition.json` — immutable plan; `init --force` to reshuffle from a new seed
- `progress.json` — `pending | in_progress | completed` per week
- `week-NN/scripts.json` — the cells dispatched that week, in the format the skill's Phase 3 dispatch consumes (one entry per cell, with role + attack inlined)

Default budget (30M Sonnet weekly × 0.9 × 50k tokens/cell = 540 cells/week → 3 weeks for the full 1110-cell matrix). Override the budget args if your plan, model behavior, or the skill's per-cell anchor changes.

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
