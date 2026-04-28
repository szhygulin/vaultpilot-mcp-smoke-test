#!/bin/bash
#
# Find which expected script IDs haven't yet been written as transcripts.
# Useful during dispatch to identify which subagents are still in flight
# (or stuck) before declaring a run complete.
#
# Usage:
#   tools/find_missing_transcripts.sh <scripts.json> [<workdir>]
#
# Reads expected IDs from <scripts.json> (any of the test-vectors shapes:
# scripts[].id, initial[].id, expansion[].id are all collected) and lists
# which IDs do NOT have a corresponding <workdir>/transcripts/<ID>.txt.
#
set -euo pipefail
SCRIPTS_JSON="${1:?usage: $0 <scripts.json> [<workdir>]}"
WORKDIR="${2:-.}"

python3 -c "
import json, os, sys
data = json.load(open('$SCRIPTS_JSON'))
ids = []
for key in ('scripts', 'initial', 'expansion'):
    for s in data.get(key, []) or []:
        if 'id' in s:
            ids.append(s['id'])
ids = sorted(set(ids))
have = set()
t_dir = os.path.join('$WORKDIR', 'transcripts')
if os.path.isdir(t_dir):
    have = {f.replace('.txt','') for f in os.listdir(t_dir) if f.endswith('.txt')}
missing = [i for i in ids if i not in have]
print(f'expected: {len(ids)}, present: {len(have & set(ids))}, missing: {len(missing)}')
for m in missing:
    print(f'  {m}')
"
