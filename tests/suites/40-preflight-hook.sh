#!/bin/bash
# 40-preflight-hook.sh — exercises .claude/hooks/preflight_gate.sh.
# Verifies:
#   - No progress.json → exit 0 (passthrough)
#   - In-progress batch, no stamp → exit 1 with stderr message
#   - In-progress batch, stamp present → exit 0
#   - Batch in 'paused' / 'completed' status → exit 0
#   - Stderr message includes the stamp path (so the orchestrator knows
#     where to touch)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 40: preflight hook ==="

HOOK="$REPO_ROOT/.claude/hooks/preflight_gate.sh"
assert_file_exists "$HOOK" "hook script exists"

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

# Test 1: no progress.json → exit 0
cd "$TMP"
set +e
"$HOOK" >/dev/null 2>&1
EC=$?
set -e
assert_exit_code 0 "$EC" "no progress.json → exit 0 (passthrough)"

# Test 2: in_progress batch, no stamp → exit 1 with stderr message
write_synth_progress "$TMP/runs/matrix-sampled/progress.json" 99 in_progress
set +e
STDERR=$("$HOOK" 2>&1 >/dev/null)
EC=$?
set -e
assert_exit_code 1 "$EC" "in_progress, no stamp → exit 1"
assert_contains "$STDERR" "BLOCKED" "stderr starts with BLOCKED"
assert_contains "$STDERR" "batch 99" "stderr names the batch"
assert_contains "$STDERR" "runs/matrix-sampled/batch-99/.preflight-confirmed" "stderr names the stamp path"
assert_contains "$STDERR" "touch" "stderr instructs to touch the stamp"

# Test 3: in_progress batch, stamp present → exit 0
mkdir -p "$TMP/runs/matrix-sampled/batch-99"
touch "$TMP/runs/matrix-sampled/batch-99/.preflight-confirmed"
set +e
"$HOOK" >/dev/null 2>&1
EC=$?
set -e
assert_exit_code 0 "$EC" "in_progress, stamp present → exit 0"

# Test 4: batch in 'paused' status → exit 0 (no in_progress to gate)
write_synth_progress "$TMP/runs/matrix-sampled/progress.json" 99 paused
rm -f "$TMP/runs/matrix-sampled/batch-99/.preflight-confirmed"  # ensure no stamp
set +e
"$HOOK" >/dev/null 2>&1
EC=$?
set -e
assert_exit_code 0 "$EC" "paused status → exit 0 (gate doesn't apply)"

# Test 5: batch in 'completed' status → exit 0
write_synth_progress "$TMP/runs/matrix-sampled/progress.json" 99 completed
set +e
"$HOOK" >/dev/null 2>&1
EC=$?
set -e
assert_exit_code 0 "$EC" "completed status → exit 0"

cd "$REPO_ROOT"
echo ""
