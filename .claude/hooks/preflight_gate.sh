#!/bin/bash
# .claude/hooks/preflight_gate.sh — PreToolUse hook for Agent calls.
#
# Blocks Agent dispatches during smoke-test batches that have NOT been
# explicitly confirmed by the user. The user confirms by `touch`ing the
# .preflight-confirmed stamp file, which the orchestrator only does AFTER
# surfacing the cost preflight (Phase 2.5) and getting an explicit "go".
#
# Exit codes:
#   0 — let the Agent call through (no smoke-test batch in progress, OR stamp exists).
#   1 — block the Agent call and surface the reason via stderr.
#
# How it integrates with the rest of the pipeline:
#   - tools/sample_matrix_run.py next-batch  →  marks a batch in_progress.
#   - /run-batch slash command surfaces preflight, asks user, on OK runs:
#       touch runs/matrix-sampled/batch-NN/.preflight-confirmed
#   - This hook runs before every `Agent` tool call. Reads progress.json,
#     finds the in-progress batch, checks for the stamp.
#   - When the batch completes (mark-completed), the next batch's preflight
#     is required again. Stamps are per-batch.
#
# Trade-off (documented in CLAUDE.md): this hook fires on EVERY Agent call
# while a batch is in_progress, including non-smoke-test ones. If you need
# a non-smoke-test Agent call mid-batch, complete or pause the batch first
# (delete the stamp + reset progress.json's in_progress entry).

set -euo pipefail

progress="runs/matrix-sampled/progress.json"

# No partition yet → no smoke test in flight → let through.
if [[ ! -f "$progress" ]]; then
    exit 0
fi

# Pick the first in_progress batch. If none, no gate to enforce.
batch=$(jq -r '.batches[]? | select(.status=="in_progress") | .batch' "$progress" 2>/dev/null | head -1)
if [[ -z "$batch" ]]; then
    exit 0
fi

pad=$(printf '%02d' "$batch")
stamp="runs/matrix-sampled/batch-${pad}/.preflight-confirmed"

if [[ -f "$stamp" ]]; then
    exit 0
fi

# No stamp → block. Stderr message tells the orchestrator what to do.
cat >&2 <<EOF
BLOCKED by .claude/hooks/preflight_gate.sh:
  batch ${batch} is in_progress but has no preflight stamp at ${stamp}.

To proceed:
  1. Surface the cost preflight (Phase 2.5) to the user.
  2. Get an explicit OK on this specific batch.
  3. Run: touch ${stamp}
  4. Retry the Agent call.

To bypass (non-smoke-test Agent work mid-batch):
  - Complete or pause the batch: jq '.batches[] |= (if .status=="in_progress" then .status="paused" else . end)' ${progress} > /tmp/p.json && mv /tmp/p.json ${progress}
  - Or delete the stamp file when done: rm ${stamp}

This hook exists because CLAUDE.md mandates per-batch cost-preflight
confirmation, and prior runs (batch-2 in this repo) showed the orchestrator
can mentally skip the gate. The hook physically prevents that.
EOF
exit 1
