#!/bin/bash
# 70-file-batch-issues.sh — exercises tools/file_batch_issues.py.
# Verifies:
#   - Default --dry-run prints all issues, one per line, with [attr] [labels] title shape
#   - --exclude N,M skips those indices and adjusts the count
#   - --only and --exclude together → exit 1 (mutually exclusive)
#   - Missing attribution field falls back to [mcp-defect] in dry-run output
#   - Out-of-range --exclude indices don't crash (no-op)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 70: file-batch-issues ==="

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

# Stage a temp REPO_ROOT — file_batch_issues.py computes REPO_ROOT from its
# own __file__ location, so copying it to $TMP/tools/ makes $TMP the resolved
# REPO_ROOT and runs/matrix-sampled/batch-99/ resolves under $TMP.
mkdir -p "$TMP/tools" "$TMP/runs/matrix-sampled/batch-99"
cp "$REPO_ROOT/tools/file_batch_issues.py" "$TMP/tools/"
cp "$REPO_ROOT/tests/fixtures/file-batch-issues/issues.draft.json" \
   "$TMP/runs/matrix-sampled/batch-99/issues.draft.json"

cd "$TMP"

# Test 1: plain --dry-run — all 3 issues print, count line correct
set +e
OUT=$(python3 tools/file_batch_issues.py --batch 99 --repo synth/repo --dry-run 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "plain --dry-run → exit 0"
assert_contains "$OUT" "Filing 3 of 3" "dry-run reports filing 3 of 3"
assert_contains "$OUT" "[mcp-defect]" "issue #1 attribution rendered"
assert_contains "$OUT" "[advisory-injection-shaped]" "issue #2 attribution rendered"
assert_contains "$OUT" "Synth issue #1" "issue #1 title rendered"
assert_contains "$OUT" "Synth issue #3" "issue #3 title rendered (back-compat)"
DRY_LINE_COUNT=$(echo "$OUT" | grep -c "\[dry-run\]" || true)
assert_equals "3" "$DRY_LINE_COUNT" "exactly 3 [dry-run] lines"

# Test 2: --exclude 2,3 skips those, files only #1
set +e
OUT=$(python3 tools/file_batch_issues.py --batch 99 --repo synth/repo --dry-run --exclude 2,3 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "--exclude 2,3 → exit 0"
assert_contains "$OUT" "Filing 1 of 3" "dry-run reports filing 1 of 3 with --exclude 2,3"
assert_contains "$OUT" "Synth issue #1" "non-excluded issue #1 still printed"
assert_not_contains "$OUT" "Synth issue #2" "excluded issue #2 absent"
assert_not_contains "$OUT" "Synth issue #3" "excluded issue #3 absent"

# Test 3: --only and --exclude together → exit 1
set +e
OUT=$(python3 tools/file_batch_issues.py --batch 99 --repo synth/repo --dry-run --only 1 --exclude 2 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "--only + --exclude → exit 1"
assert_contains "$OUT" "mutually exclusive" "stderr explains mutual exclusivity"

# Test 4: back-compat — issue #3 has no attribution, dry-run shows [mcp-defect]
# (already covered by Test 1's assert_contains "[mcp-defect]" but make it explicit:
# the rendered line for issue #3 specifically must show mcp-defect, not blank
# or "—".)
set +e
OUT=$(python3 tools/file_batch_issues.py --batch 99 --repo synth/repo --dry-run 2>&1)
EC=$?
set -e
LINE3=$(echo "$OUT" | grep "Synth issue #3" || true)
assert_contains "$LINE3" "[mcp-defect]" "missing-attribution falls back to mcp-defect"
assert_contains "$LINE3" "[bug_report]" "missing-attribution still prints labels"

# Test 5: out-of-range --exclude doesn't crash
set +e
OUT=$(python3 tools/file_batch_issues.py --batch 99 --repo synth/repo --dry-run --exclude 99 2>&1)
EC=$?
set -e
assert_exit_code 0 "$EC" "--exclude 99 (out-of-range) → exit 0"
assert_contains "$OUT" "Filing 3 of 3" "out-of-range exclude is a no-op"

cd "$REPO_ROOT"
echo ""
