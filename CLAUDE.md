# Project rules for Claude

## Git workflow

**Never push directly to `main`.** Even when the remote accepts the push (bypass rights exist on this repo), the branch is protected and the maintainer expects all changes to go through pull requests.

When asked to "commit and push", interpret that as:

1. Create a feature branch (`git checkout -b <short-descriptive-name>`).
2. Commit the changes there.
3. Push the branch with `-u` to set upstream.
4. Open a PR with `gh pr create` and return the PR URL.

If you're already sitting on `main` with local commits when this comes up, move them to a new branch before pushing — do not push `main` directly. Reset `main` to `origin/main` only after the new branch is in place and pushed.

## mcp-smoke-test skill is binding

When the `mcp-smoke-test` skill is loaded (it lives at `skill/SKILL.md` in this repo and is symlinked/installed at `~/.claude/skills/mcp-smoke-test/`), every instruction in it is **mandatory**, not advisory. In particular:

- **Phase 2.5 cost preflight is a hard gate, fires on every single batch.** Never dispatch a batch without first surfacing the cost preflight block (sample, role distribution, out-of-scope/control share, Haiku throughput, Opus analysis cost, wall-clock estimate, filing target) AND getting an explicit user OK on that specific batch. A "go" on batch N does NOT authorize batch N+1 — each batch's role distribution and scope share differ; the user must re-confirm with eyes on the actual numbers for that batch. Running `next-batch` prints the block as a side effect, but printing is not confirming — pause for user OK before any Agent dispatch.
- **Use the pre-approved helper subcommands** (`inspect-batch`, `verify-transcripts`, `mark-completed`, `aggregate-batch`, `next-batch`, `status`) instead of ad-hoc `python3 -c "..."` whenever the helper covers the operation. Each ad-hoc Python invocation triggers a fresh permission prompt; the helpers are already in the user's approved set.
- **Don't skip steps** in the 6-phase pipeline (Catalog → Generate → Cost preflight → Spawn → Concat → Analyze → File). Phases 1, 4, 6 are mode-independent; Phases 2, 3, 5 branch by mode (honest vs. adversarial). Cost preflight (2.5) is mandatory in both modes.
- **A.5 / C.5 findings never go in `issues.draft.json`.** They route to the §7 upstream-escalation note (chat-client output filter for injection-shaped, model-layer safety for model-shaped). Filing them as MCP/skill defects produces security theater per issue #21.
- If a skill instruction conflicts with what looks faster or simpler, the skill wins. Surface the conflict to the user before deviating.

## Preflight gate (PreToolUse hook on `Agent`)

The Phase 2.5 cost-preflight rule above is enforced by a **PreToolUse hook** at `.claude/hooks/preflight_gate.sh`, registered in `.claude/settings.json`. The hook physically blocks `Agent` tool calls during a smoke-test batch unless the batch's `.preflight-confirmed` stamp file exists.

Flow:

1. `python3 tools/sample_matrix_run.py next-batch` writes `runs/matrix-sampled/batch-NN/scripts.json` and marks the batch `in_progress` in `progress.json`.
2. The orchestrator surfaces the cost preflight block to the user (sample, role distribution, A.5/C.5 share, E control share, Haiku throughput, Opus analysis cost, wall-clock estimate, filing target).
3. **User says "go" / "OK"** explicitly for THIS batch.
4. The orchestrator runs `touch runs/matrix-sampled/batch-NN/.preflight-confirmed`. This `touch` is the only place the stamp is created and is pre-approved in `.claude/settings.json`.
5. Subsequent `Agent` calls pass the hook (stamp present).

If the orchestrator forgets step 2-3 and tries to dispatch directly, the hook exits 1 with a stderr message naming the missing stamp. The orchestrator must then go back to step 2.

**Bypass for non-smoke-test work mid-batch**: if you need an `Agent` call unrelated to the batch while a batch is in_progress (rare in this single-purpose repo), either complete/pause the batch first, or delete the stamp + reset the in_progress entry temporarily. Documented in the hook script's stderr output.

**Why this hook exists**: prior session (batch-2 in this repo) showed the orchestrator can mentally skip the cost-preflight rule even when CLAUDE.md says "mandatory". The hook makes the gate physical, not advisory.
