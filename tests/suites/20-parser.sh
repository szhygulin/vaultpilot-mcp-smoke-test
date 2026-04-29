#!/bin/bash
# 20-parser.sh — exercises tools/sample_matrix_run.py's _parse_transcripts
# against fixture transcripts. Verifies the Lane 1 parser fixes:
#   - Pipe-delimited header `\| ROLE:` matcher (NOT the old `\bROLE:` that
#     mis-matched "MCP ROLE:" in notes prose)
#   - parse_failures correctly populated when fields missing
#   - outcome_status, refusal_class, a5_attribution extraction

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/helpers.sh"

echo ""
echo "=== Suite 20: parser ==="

TMP=$(mktempdir)
trap 'cleanup_tempdir "$TMP"' EXIT

# Setup: copy each fixture into a transcripts/ dir, parse, inspect output.
TRANSCRIPTS="$TMP/transcripts"
mkdir -p "$TRANSCRIPTS"
cp "$REPO_ROOT/tests/fixtures/well-formed.txt" "$TRANSCRIPTS/"
cp "$REPO_ROOT/tests/fixtures/missing-refusal-class.txt" "$TRANSCRIPTS/"
cp "$REPO_ROOT/tests/fixtures/role-poisoned-by-notes.txt" "$TRANSCRIPTS/"

# Run parser, capture per-record fields as JSON for assertion.
PARSED_JSON=$(python3 - <<PYEOF
import sys, json
sys.path.insert(0, '$REPO_ROOT/tools')
from sample_matrix_run import _parse_transcripts
recs = _parse_transcripts('$TRANSCRIPTS')
out = {}
for r in recs:
    out[r['file']] = {
        'role': r['role'],
        'outcome_status': r['outcome_status'],
        'refusal_class': r['refusal_class'],
        'defense_layer': r['defense_layer'],
        'did_user_get_tricked': r['did_user_get_tricked'],
        'a5_attribution': r['a5_attribution'],
        'parse_failure_count': len(r['parse_failures']),
        'parse_failure_fields': sorted({pf['field'] for pf in r['parse_failures']}),
    }
print(json.dumps(out, indent=2))
PYEOF
)

# Spot-check well-formed
assert_equals "A.4"      "$(echo "$PARSED_JSON" | jq -r '."well-formed.txt".role')"           "well-formed: role A.4"
assert_equals "refused"  "$(echo "$PARSED_JSON" | jq -r '."well-formed.txt".outcome_status')" "well-formed: status refused"
assert_equals "security" "$(echo "$PARSED_JSON" | jq -r '."well-formed.txt".refusal_class')"  "well-formed: refusal_class security"
assert_equals "no"       "$(echo "$PARSED_JSON" | jq -r '."well-formed.txt".did_user_get_tricked')" "well-formed: tricked no"
assert_equals "0"        "$(echo "$PARSED_JSON" | jq -r '."well-formed.txt".parse_failure_count')"   "well-formed: 0 parse failures"

# missing-refusal-class: status=refused but no refusal_class field
assert_equals "B"        "$(echo "$PARSED_JSON" | jq -r '."missing-refusal-class.txt".role')"           "missing-rc: role B"
assert_equals "refused"  "$(echo "$PARSED_JSON" | jq -r '."missing-refusal-class.txt".outcome_status')" "missing-rc: status refused"
assert_equals "unknown"  "$(echo "$PARSED_JSON" | jq -r '."missing-refusal-class.txt".refusal_class')"  "missing-rc: refusal_class unknown"
assert_equals "1"        "$(echo "$PARSED_JSON" | jq -r '."missing-refusal-class.txt".parse_failure_count')" "missing-rc: 1 parse failure"
assert_equals '["refusal_class"]' "$(echo "$PARSED_JSON" | jq -c '."missing-refusal-class.txt".parse_failure_fields')" "missing-rc: refusal_class flagged"

# role-poisoned-by-notes: regression test for the \bROLE: → \| ROLE: fix.
# The notes contain "MCP ROLE:" — old parser matched it, new parser doesn't.
assert_equals "C.4"      "$(echo "$PARSED_JSON" | jq -r '."role-poisoned-by-notes.txt".role')" "role-poisoned: role correctly C.4 (not unknown)"
assert_equals "0"        "$(echo "$PARSED_JSON" | jq -r '."role-poisoned-by-notes.txt".parse_failure_count')" "role-poisoned: 0 parse failures (parser doesn't mis-match notes)"

echo ""
