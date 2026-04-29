#!/bin/bash
# 60-verify-transcripts.sh — exercises sample_matrix_run.py's
# cmd_verify_transcripts.
# Verifies:
#   - Clean transcripts pass with exit 0
#   - --repair inserts [ADVERSARIAL_RESULT] when missing
#   - --repair synthesizes a minimal block when role: line is also missing

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 60: verify-transcripts ==="

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

mkdir -p "$TMP/runs/matrix-sampled/batch-99/transcripts" "$TMP/tools"
cp "$REPO_ROOT/tools/sample_matrix_run.py" "$TMP/tools/"

# Test 1: clean transcripts → exit 0, no patches needed
cp "$REPO_ROOT/tests/fixtures/well-formed.txt" "$TMP/runs/matrix-sampled/batch-99/transcripts/"
cd "$TMP"
set +e
OUT=$(python3 tools/sample_matrix_run.py verify-transcripts --batch 99 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "clean transcripts → exit 0"
assert_contains "$OUT" "ok:           1" "all 1 transcripts ok"

# Test 2: missing [ADVERSARIAL_RESULT] header → exit 1 without --repair
cat > "$TMP/runs/matrix-sampled/batch-99/transcripts/synth-missing-header.txt" <<'EOF'
SCRIPT_ID: synth-missing-header | CATEGORY: x | CHAIN: y | ROLE: A.4
ATTACK: test
SCRIPT: test

[OUTCOME]
status: refused
reason: x

role: A.4
attack_attempted: x
defense_layer: invariant-1
did_user_get_tricked: no
notes: header missing
EOF

set +e
OUT=$(python3 tools/sample_matrix_run.py verify-transcripts --batch 99 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "missing header without --repair → exit 1"
assert_contains "$OUT" "missing header" "stderr names the missing-header issue"

# Test 3: --repair patches the missing header
set +e
OUT=$(python3 tools/sample_matrix_run.py verify-transcripts --batch 99 --repair 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "--repair fixes missing header → exit 0"
assert_contains "$OUT" "patched:" "repair: at least one patched"
assert_file_contains "$TMP/runs/matrix-sampled/batch-99/transcripts/synth-missing-header.txt" "[ADVERSARIAL_RESULT]" "patched file now has [ADVERSARIAL_RESULT]"

# Test 4: re-running --repair on already-fixed transcripts is idempotent
set +e
OUT=$(python3 tools/sample_matrix_run.py verify-transcripts --batch 99 --repair 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "--repair idempotent on already-fixed → exit 0"
assert_contains "$OUT" "ok:           2" "both transcripts pass on second run"

cd "$REPO_ROOT"
echo ""
