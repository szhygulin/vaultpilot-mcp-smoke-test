#!/bin/bash
# 90-prepare-dispatch.sh — exercises tools/prepare_dispatch.py.
# Verifies:
#   - Builds prompts for all cells in scripts.json in one call
#   - Output JSON has correct shape (prompts_dir, cell_ids, cell_count)
#   - Per-cell files exist and match what build_dispatch_prompt.py emits
#     individually (regression: single source of truth)
#   - Missing scripts.json → exit 1 with clear error

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 90: prepare-dispatch ==="

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

FIXTURE="$REPO_ROOT/tests/fixtures/dispatch-prompt/cells.json"
HELPER="$REPO_ROOT/tools/prepare_dispatch.py"
BUILDER="$REPO_ROOT/tools/build_dispatch_prompt.py"

# Test 1: plain run on fixture, custom output-dir → exit 0, JSON shape
OUT_DIR="$TMP/prompts"
OUT=$(python3 "$HELPER" --batch 99 --scripts "$FIXTURE" --output-dir "$OUT_DIR")
EC=$?
assert_exit_code 0 "$EC" "plain run → exit 0"
# JSON shape
PROMPTS_DIR=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin)['prompts_dir'])")
CELL_COUNT=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin)['cell_count'])")
FIRST_CELL=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin)['cell_ids'][0])")
assert_equals "$OUT_DIR" "$PROMPTS_DIR" "JSON prompts_dir matches --output-dir"
assert_equals "5" "$CELL_COUNT" "JSON cell_count = 5 (fixture size)"
assert_equals "synth-001-A.1" "$FIRST_CELL" "JSON cell_ids[0] matches fixture order"

# Test 2: per-cell files exist
assert_file_exists "$OUT_DIR/synth-001-A.1.txt" "A.1 prompt file"
assert_file_exists "$OUT_DIR/synth-002-A.5.txt" "A.5 prompt file"
assert_file_exists "$OUT_DIR/synth-003-D.txt" "D prompt file"
assert_file_exists "$OUT_DIR/synth-004-E.txt" "E prompt file"
assert_file_exists "$OUT_DIR/synth-005-F.txt" "F prompt file"

# Test 3: per-cell file content matches what builder emits individually
EXPECTED=$(python3 "$BUILDER" --batch 99 --scripts "$FIXTURE" --cell-id synth-001-A.1)
ACTUAL=$(cat "$OUT_DIR/synth-001-A.1.txt")
assert_equals "$EXPECTED" "$ACTUAL" "A.1 prompt file matches builder stdout (single source of truth)"

# Test 4: missing scripts.json → exit 1 with clear error
set +e
OUT=$(python3 "$HELPER" --batch 99 --scripts "$TMP/nonexistent.json" 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "missing scripts.json → exit 1"
assert_contains "$OUT" "scripts.json not found" "stderr names the missing path"

# Test 5: scripts.json with no cells → exit 1
echo '{"scripts": []}' > "$TMP/empty-scripts.json"
set +e
OUT=$(python3 "$HELPER" --batch 99 --scripts "$TMP/empty-scripts.json" 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "empty scripts.json → exit 1"
assert_contains "$OUT" "no cells" "stderr explains empty case"

# Test 6: scripts.json with malformed cell → exit 1
echo '{"scripts": [{"id": "bad-cell"}]}' > "$TMP/bad-scripts.json"
set +e
OUT=$(python3 "$HELPER" --batch 99 --scripts "$TMP/bad-scripts.json" --output-dir "$TMP/bad-out" 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "malformed cell → exit 1"
assert_contains "$OUT" "build_prompt failed" "stderr names the failure"

echo ""
