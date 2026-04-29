#!/bin/bash
# 80-dispatch-prompt.sh — exercises tools/build_dispatch_prompt.py.
# Verifies:
#   - Builder emits a prompt with required structural elements
#   - Tool-discipline section present (Read tool > Bash cat; 20-call cap; reply-only-wrote-path; no pushback)
#   - Per-role specialization (A.5 a5_attribution required; D mentions preflight-step-0; E mentions ALL HONEST; F mentions rogue RPC)
#   - Save path matches the requested batch number
#   - Builder rejects malformed cells (missing required keys) with exit 1

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 80: dispatch-prompt builder ==="

FIXTURE="$REPO_ROOT/tests/fixtures/dispatch-prompt/cells.json"
BUILDER="$REPO_ROOT/tools/build_dispatch_prompt.py"

# Test 1: A.1 cell — required structural elements + tool-discipline
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-001-A.1)
assert_contains "$OUT" "SCRIPT_ID: synth-001-A.1" "A.1: SCRIPT_ID line"
assert_contains "$OUT" "ROLE: A.1" "A.1: role header"
assert_contains "$OUT" "[USER]" "A.1: USER block"
assert_contains "$OUT" "[ADVERSARIAL_RESULT]" "A.1: ADVERSARIAL_RESULT block"
assert_contains "$OUT" "TOOL DISCIPLINE" "A.1: tool discipline section"
assert_contains "$OUT" "Use the Read tool" "A.1: read-tool guidance"
assert_contains "$OUT" "Do NOT use Bash with" "A.1: no-bash-cat guidance"
assert_contains "$OUT" "20 substantive tool calls" "A.1: 20-call hard cap"
assert_contains "$OUT" "wrote " "A.1: reply-only-wrote-path rule"
assert_contains "$OUT" "Do NOT ask for clarification" "A.1: no-pushback rule"

# Test 2: A.5 cell — a5_attribution REQUIRED, with both choices
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-002-A.5)
assert_contains "$OUT" "ROLE: A.5" "A.5: role header"
assert_contains "$OUT" "<injection-shaped | model-shaped>   (REQUIRED for A.5)" "A.5: a5_attribution required for A.5"
assert_contains "$OUT" "Advisory-text-only" "A.5: role guidance present"

# Test 3: D cell — preflight-step-0 framing
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-003-D)
assert_contains "$OUT" "ROLE: D" "D: role header"
assert_contains "$OUT" "preflight-step-0" "D: defense_layer guidance mentions preflight-step-0"
assert_contains "$OUT" "Supply-chain skill tamper" "D: role guidance present"
assert_contains "$OUT" "a5_attribution: n/a" "D: a5_attribution n/a (not advisory)"

# Test 4: E (control) cell — ALL HONEST + false-positive framing
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-004-E)
assert_contains "$OUT" "ROLE: E" "E: role header"
assert_contains "$OUT" "ALL HONEST" "E: control framing"
assert_contains "$OUT" "false-positive" "E: false-positive framing"
assert_contains "$OUT" "attack_attempted: none" "E: attack_attempted: none"

# Test 5: F cell — rogue RPC framing
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-005-F)
assert_contains "$OUT" "ROLE: F" "F: role header"
assert_contains "$OUT" "Rogue RPC" "F: rogue-RPC framing"
assert_contains "$OUT" "MCP relays unchanged" "F: MCP-honest framing"

# Test 6: Save path matches the requested batch number
OUT=$(python3 "$BUILDER" --scripts "$FIXTURE" --cell-id synth-001-A.1 --workdir /tmp/test-batch-99)
assert_contains "$OUT" "/tmp/test-batch-99/synth-001-A.1.txt" "save path honors --workdir override"

# Test 7: Malformed cell → exit 1 with clear error
TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT
cat > "$TMP/bad-cells.json" <<'EOF'
{"scripts": [{"id": "broken", "role": "A.1"}]}
EOF
set +e
OUT=$(python3 "$BUILDER" --scripts "$TMP/bad-cells.json" --cell-id broken 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "malformed cell → exit 1"
assert_contains "$OUT" "missing required keys" "stderr names the missing keys"

# Test 8: --batch and --scripts are mutually exclusive
set +e
OUT=$(python3 "$BUILDER" --batch 1 --scripts "$FIXTURE" --cell-id synth-001-A.1 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "--batch + --scripts → exit 1"
assert_contains "$OUT" "mutually exclusive" "stderr explains mutual exclusivity"

# Test 9: missing both --batch and --scripts → exit 1
set +e
OUT=$(python3 "$BUILDER" --cell-id synth-001-A.1 2>&1)
EC=$?
set -e
assert_exit_code 1 "$EC" "missing both → exit 1"
assert_contains "$OUT" "required" "stderr explains one is required"

echo ""
