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
- **Smoke-test scope is UX + correctness + security, not just security.** When the agent emits a typosquat URL, hallucinated address, sycophantic "yes that's safe" capitulation, wrong explanation, confusing prose, or any harmful/incorrect output — that's a finding. This applies most often to **A.5 / C.5** (advisory-text-only roles, where the harmful payload IS the prose) but also to **honest-agent rows** where the flow ran correctly mechanically but the user-visible answer was wrong / confusing / unhelpful.
- **Out-of-scope for `issues.draft.json` filing ≠ out-of-scope for the test.** A.5 / C.5 don't go in `issues.draft.json` against `vaultpilot-mcp` — filing them there produces security theater per issue #21, because the MCP/skill layer can't refuse text it never produced. But they DO get recorded in `findings.md`: A.5 / C.5 in §7 (split A.5a injection-shaped → chat-client output filter, A.5b model-shaped → model-layer safety); honest-agent UX/correctness issues in §3 (critical findings) or a dedicated UX subsection. **Never silently drop a finding because it can't be filed against the MCP** — the test owner needs to see it regardless.
- If a skill instruction conflicts with what looks faster or simpler, the skill wins. Surface the conflict to the user before deviating.
