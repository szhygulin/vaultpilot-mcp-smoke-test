# tools/

Helper scripts used during smoke-test runs. These are the little utilities the parent agent shells out to between Claude Code subagent dispatches — extracted from inline usage in the original runs so they're reusable for re-runs.

| Script | Purpose | When |
|---|---|---|
| `concat_transcripts.sh` | Bash loop concatenating `transcripts/*.txt` into a single `all_transcripts.txt` corpus | Phase 4 (between dispatch and analysis) |
| `parse_summary.py` | Python parser extracting `SCRIPT_ID/CATEGORY/CHAIN/OUTCOME/OBSERVATIONS` per transcript → `summary.txt` | Phase 5 step 5.2 (honest mode) |
| `parse_summary_adversarial.py` | Same as above, plus the `[ADVERSARIAL_RESULT]` block (role / attack / defense_layer / did_user_get_tricked) | Phase 5 step 5.2 (adversarial mode) |
| `find_missing_transcripts.sh` | Diff between expected script IDs (from a `scripts.json`) and on-disk `transcripts/*.txt` — surfaces which subagents haven't completed yet | Phase 3 monitoring |
| `wait_for_transcripts.sh` | Block until a target transcript count is reached. Designed for `Bash(run_in_background:true)` so the parent agent gets a single "all done" notification | Phase 3 / 4 transition |

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
