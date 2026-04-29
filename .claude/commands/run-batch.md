---
description: Run one full smoke-test batch end-to-end (preflight → dispatch → analyze → file → commit). Two user gates only.
---

# /run-batch — autonomous smoke-test batch

Runs the next pending batch of the vaultpilot-mcp adversarial smoke test through the full 6-phase pipeline (per `skill/SKILL.md`, soon `CLAUDE.md` per Lane 2). One slash invocation, two manual user gates, everything else automatic.

## Manual gates (the only places you'll be asked anything)

1. **Cost preflight gate.** After `next-batch` prints the per-batch role distribution + Opus analysis cost + filing target, you'll be asked for explicit OK on this specific batch. A "go" on batch N does NOT carry over to batch N+1 (per CLAUDE.md).
2. **Filing dry-run gate.** After Phase 5 produces `findings.md` + `issues.draft.json`, the filer dry-runs and surfaces the planned issue titles + label sets. You'll be asked one OK on the full set; on OK, all issues file in one go.

## Steps the orchestrator follows verbatim

1. **`python3 tools/sample_matrix_run.py next-batch`** — writes `runs/matrix-sampled/batch-NN/scripts.json`, prints the cost preflight block, marks batch in_progress.
2. **GATE 1 — surface preflight, ask user.** Format the cost preflight as a markdown table (sample, role distribution, A.5/C.5 share, E control share, Haiku throughput, Opus analysis cost, wall-clock estimate, filing target). Ask: "Explicit OK to dispatch all N cells?". Wait for affirmative.
3. **`touch runs/matrix-sampled/batch-NN/.preflight-confirmed`** — stamp file. Lane 3's PreToolUse hook checks for this; without it, `Agent` calls are blocked.
4. **Dispatch.** Read full cell list from `runs/matrix-sampled/batch-NN/scripts.json`. Spawn parallel `Agent` calls in waves of 25 (single message per wave with 25 tool_use blocks): `subagent_type: general-purpose`, `model: haiku`, prompt = adversarial-mode template with `{id, role, category, chain, script, attack}` substituted. Each subagent uses its own Write tool to save its transcript at `runs/matrix-sampled/batch-NN/transcripts/{id}.txt`; reply is just `wrote <path>`.
5. **`python3 tools/sample_matrix_run.py verify-transcripts --batch NN --repair`** — checks every transcript has the literal `[ADVERSARIAL_RESULT]` header; auto-repairs if missing.
6. **`python3 tools/sample_matrix_run.py mark-completed --batch NN`** — marks completed in `progress.json` and auto-runs the aggregate (writes `summary.txt` + `aggregate.json`).
7. **Phase 5 analysis subagent.** Spawn one `Agent` call: `subagent_type: general-purpose`, `model: opus`, prompt = canonical Phase 5 prompt (filling in `<MCP-NAME>` and `<workdir>`). Subagent reads `summary.txt` + selectively reads `transcripts/*.txt` + cross-references prior-batch findings. Returns markdown analysis + a fenced ```json-issues-draft``` block.
8. **Persist analysis.** Parent agent writes the markdown to `runs/matrix-sampled/batch-NN/findings.md` and the JSON to `runs/matrix-sampled/batch-NN/issues.draft.json`.
9. **`python3 tools/file_batch_issues.py --batch NN --repo szhygulin/vaultpilot-mcp --dry-run`** — preview the planned `gh issue create` calls.
10. **GATE 2 — surface dry-run summary, ask user.** Show the planned issue titles + label sets in a markdown table. Ask: "OK to file all N issues against szhygulin/vaultpilot-mcp?". Wait for affirmative.
11. **`python3 tools/file_batch_issues.py --batch NN --repo szhygulin/vaultpilot-mcp`** — files all issues, appends URLs to `runs/matrix-sampled/batch-NN/issues.md`.
12. **`tools/post_batch_commit.sh NN`** — branches (`batch-NN-results`), commits batch-NN artifacts + `progress.json`, pushes, opens PR.
13. **Report final summary.** Tell the user: batches done, issue URLs filed, PR URL.

## What you DON'T need to confirm during this flow

- Each individual Agent dispatch (covered by the preflight stamp + Lane 3 hook).
- `verify-transcripts --repair` (deterministic auto-fix, idempotent).
- `mark-completed` (no side effects beyond local files).
- Phase 5 Opus analyst spawn (one call, ~82k tokens, already in the cost preflight).
- Each individual `gh issue create` call (covered by GATE 2's full-set OK).
- Branch + commit + push + PR-open (auto on this repo per CLAUDE.md "never push to main"; auto-commits go to a feature branch).

## What to do if a step fails

- **`Agent` call blocked by preflight hook (Lane 3):** the stamp file is missing or the user wasn't asked. Surface the cost preflight, get OK, `touch` the stamp, retry.
- **`verify-transcripts --repair` reports failures it can't fix:** stop and surface the failing transcripts to the user. Don't silently drop them; offer revert (re-run the cell, accept synthesized minimal block, or skip with explicit acknowledgement).
- **Phase 5 analysis subagent returns malformed JSON:** parse-then-show-the-user; ask whether to re-run or hand-edit `issues.draft.json`.
- **`gh issue create` fails on a label:** the label isn't on the target repo. Surface the missing label name; user creates it (or you propose a substitute) before retry.
- **`tools/post_batch_commit.sh` fails on push (e.g. main branch protection violation):** never force; surface the error, the user resolves manually.

## When NOT to use this command

- One-off experimentation that doesn't follow the standard 50-cell batch flow.
- Re-running a batch that's already in `completed` status (you'd want `aggregate-batch` only, then re-trigger Phase 5 manually).
- Filing into a different repo than `szhygulin/vaultpilot-mcp` (override with `--repo` flag once you reach the filing step).
