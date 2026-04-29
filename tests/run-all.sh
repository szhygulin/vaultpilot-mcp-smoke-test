#!/bin/bash
# tests/run-all.sh — entry point for the mock test suite.
#
# Runs every suite under tests/suites/ in lexical order, accumulates
# pass/fail counts, exits 0 if all pass and non-zero on any failure.
#
# Usage:
#   ./tests/run-all.sh
#
# What this suite covers:
# - tools/sample_matrix_run.py canonicalizers, parser, aggregator
# - .claude/hooks/preflight_gate.sh
# - cmd_next_batch (validation + workdir setup)
# - cmd_verify_transcripts (--repair behavior)
#
# What this suite explicitly does NOT cover:
# - Real Agent dispatches (no LLM calls)
# - Real Phase 5 Opus analysis (no LLM calls)
# - Real `gh issue create` against vaultpilot-mcp (no GitHub side effects)
# - Real `git push` to origin (no remote side effects)
# - The /run-batch slash command end-to-end (not directly testable as a script;
#   each step it orchestrates IS tested individually here)
#
# Why mock-only: this suite is meant to catch regressions in the orchestration
# plumbing without paying the cost (or risk) of a real batch run. It runs in
# < 30 seconds and requires only python3 + jq.

set -uo pipefail  # NB: not -e; we want to run every suite even if one fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export REPO_ROOT

# Pre-flight: required tools
for cmd in python3 jq; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: $cmd is required but not installed." >&2
        exit 1
    fi
done

LOG_DIR="$SCRIPT_DIR/.last-run"
rm -rf "$LOG_DIR"
mkdir -p "$LOG_DIR"

TOTAL_PASSED=0
TOTAL_FAILED=0
FAILED_SUITES=()

cd "$REPO_ROOT"

echo "Running mock test suite from $REPO_ROOT"
echo "(suites: $(ls -1 "$SCRIPT_DIR/suites/"*.sh | wc -l) | log dir: $LOG_DIR)"

for suite in "$SCRIPT_DIR/suites/"*.sh; do
    suite_name=$(basename "$suite")
    log="$LOG_DIR/$suite_name.log"
    : > "$log"

    # Each suite runs in a subshell with its own counters.
    PASSED_COUNT=0
    FAILED_COUNT=0
    export TEST_LOG="$log"
    export PASSED_COUNT FAILED_COUNT
    set +e
    bash "$suite"
    suite_ec=$?
    set -e

    # Counts are per-suite; we extract them from the log we've been writing to.
    # `grep -c` returns "0" with exit 1 on no matches; `|| true` keeps the "0"
    # without appending a second "0" via `|| echo 0` (which broke arithmetic).
    suite_passed=$(grep -c '^  PASS:' "$log" 2>/dev/null || true)
    suite_failed=$(grep -c '^  FAIL:' "$log" 2>/dev/null || true)
    suite_passed=${suite_passed:-0}
    suite_failed=${suite_failed:-0}
    TOTAL_PASSED=$((TOTAL_PASSED + suite_passed))
    TOTAL_FAILED=$((TOTAL_FAILED + suite_failed))

    if [[ $suite_failed -gt 0 || $suite_ec -ne 0 ]]; then
        FAILED_SUITES+=("$suite_name")
    fi
done

echo ""
echo "=== Summary ==="
echo "  Passed: $TOTAL_PASSED"
echo "  Failed: $TOTAL_FAILED"
if [[ ${#FAILED_SUITES[@]} -gt 0 ]]; then
    echo "  Failed suites: ${FAILED_SUITES[*]}"
    echo ""
    echo "See per-suite logs in $LOG_DIR/"
    exit 1
fi

echo "  All suites passed."
exit 0
