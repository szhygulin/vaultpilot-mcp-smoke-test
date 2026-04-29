#!/bin/bash
# 50-next-batch.sh — exercises sample_matrix_run.py's cmd_next_batch.
# Verifies:
#   - Reads partition.json + matrix.json correctly
#   - Pre-creates the transcripts/ subdir
#   - Marks batch in_progress in progress.json
#   - Lane 1 strict-validation: malformed cells cause exit 1 with stderr details

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 50: next-batch ==="

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

# Build a self-contained mini-repo: matrix.json + partition + progress.
mkdir -p "$TMP/test-vectors" "$TMP/runs/matrix-sampled" "$TMP/tools"
write_synth_matrix "$TMP/test-vectors/matrix.json"
write_synth_partition "$TMP/runs/matrix-sampled/partition.json"
write_synth_progress "$TMP/runs/matrix-sampled/progress.json" 99 pending
cp "$REPO_ROOT/tools/sample_matrix_run.py" "$TMP/tools/"

# Test 1: happy path — next-batch produces scripts.json + transcripts/ dir
#         and marks in_progress.
cd "$TMP"
set +e
OUT=$(python3 tools/sample_matrix_run.py next-batch 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "next-batch happy path → exit 0"
assert_file_exists "$TMP/runs/matrix-sampled/batch-99/scripts.json" "scripts.json written"
[[ -d "$TMP/runs/matrix-sampled/batch-99/transcripts" ]] && _test_pass "transcripts/ pre-created" || _test_fail "transcripts/ not pre-created"

STATUS=$(jq -r '.batches[0].status' "$TMP/runs/matrix-sampled/progress.json")
assert_equals "in_progress" "$STATUS" "progress.json batch 99 status = in_progress"

# Verify scripts.json structure
SCRIPTS_JSON=$(cat "$TMP/runs/matrix-sampled/batch-99/scripts.json")
assert_contains "$SCRIPTS_JSON" '"role": "A.4"' "scripts.json has A.4 cell"
assert_contains "$SCRIPTS_JSON" '"role": "B"'   "scripts.json has B cell"

# Test 2: malformed cell — partition references a role NOT in roleLegend
write_synth_progress "$TMP/runs/matrix-sampled/progress.json" 99 pending
python3 -c "
import json
p = json.load(open('$TMP/runs/matrix-sampled/partition.json'))
# Inject a malformed cell: role 'X.99' is not in our synth roleLegend
p['batches'][0]['cells'].append({'audience': 'expert', 'row_id': 'synth-001', 'role': 'X.99'})
json.dump(p, open('$TMP/runs/matrix-sampled/partition.json', 'w'), indent=2)
"
rm -rf "$TMP/runs/matrix-sampled/batch-99"  # clear stamp dir for re-run
set +e
OUT=$(python3 tools/sample_matrix_run.py next-batch 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "next-batch malformed cell → exit 1"
assert_contains "$OUT" "ERROR" "stderr starts with ERROR"
assert_contains "$OUT" "X.99" "stderr names the bad role"
assert_contains "$OUT" "not in roleLegend" "stderr explains the issue"
assert_contains "$OUT" "Lane 1 policy" "stderr cites Lane 1 policy"

cd "$REPO_ROOT"
echo ""
