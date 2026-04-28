#!/usr/bin/env python3
"""
test-vectors/build_matrix.py — Concatenate expert-matrix.json +
newcomer-matrix.json into a single unified `matrix.json` with an explicit
`audience` field per row.

This is the single source of truth that downstream tooling
(`tools/sample_matrix_run.py`) consumes. The two source files
(`expert-matrix.json`, `newcomer-matrix.json`) remain the per-audience
authored catalogs; this script just unions them with an `audience` tag and
preserves all existing fields.

Schema (output `matrix.json`):
  {
    "_comment": "...",
    "roleLegend": {"A":"...", "B":"...", "C":"...", ...},
    "addressBook": {...},          # multi-chain dict (per multi-chain-addressbook PR)
    "rows": [
      {
        "id": "001",                         # cell ID, scoped per-audience for now
        "audience": "expert" | "newcomer",   # NEW: tags the source matrix
        "category": "send_native",
        "chain": "ethereum",                 # may be absent on newcomer rows
        "script": "...",
        "cells": {"A": "...", "B": "...", "C": "..."}
      },
      ...
    ],
    "totals": {"rows": N, "roles": 3, "cells": 3*N, "by_audience": {...}}
  }

Reproducibility: rerun this script after editing either source matrix.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__)) + '/..'
EXPERT_PATH = f'{REPO}/test-vectors/expert-matrix.json'
NEWCOMER_PATH = f'{REPO}/test-vectors/newcomer-matrix.json'
OUT_PATH = f'{REPO}/test-vectors/matrix.json'


def main() -> None:
    expert = json.load(open(EXPERT_PATH))
    newcomer = json.load(open(NEWCOMER_PATH))

    # Sanity: roleLegends should agree.
    if expert['roleLegend'] != newcomer['roleLegend']:
        sys.exit("roleLegend mismatch between expert and newcomer matrices; "
                 "reconcile before unifying.")

    # Sanity: addressBook should agree (multi-chain unified per earlier PR).
    if expert['addressBook'] != newcomer['addressBook']:
        sys.exit("addressBook mismatch between expert and newcomer matrices; "
                 "reconcile before unifying.")

    rows = []
    for r in expert['rows']:
        rows.append({**r, 'audience': 'expert'})
    for r in newcomer['rows']:
        rows.append({**r, 'audience': 'newcomer'})

    by_audience = {'expert': len(expert['rows']), 'newcomer': len(newcomer['rows'])}
    total_rows = len(rows)

    cells_total = sum(len(r['cells']) for r in rows)
    cells_by_role = {}
    for r in rows:
        for role in r['cells']:
            cells_by_role[role] = cells_by_role.get(role, 0) + 1

    out = {
        '_comment': (
            'Unified adversarial test matrix for vaultpilot-mcp smoke test. '
            'Concatenation of expert-matrix.json + newcomer-matrix.json with '
            'explicit `audience` field. Single source of truth for sampling — '
            f'rebuild via test-vectors/build_matrix.py after editing either source. '
            f'See ../skill/SKILL.md for methodology.'
        ),
        'roleLegend': expert['roleLegend'],
        'addressBook': expert['addressBook'],
        'rows': rows,
        'totals': {
            'rows': total_rows,
            'roles_in_legend': len(expert['roleLegend']),
            'cells': cells_total,
            'cells_by_role': cells_by_role,
            'by_audience': by_audience,
        },
    }

    with open(OUT_PATH, 'w') as f:
        json.dump(out, f, indent=2)

    print(f"wrote {OUT_PATH}: {cells_total} cells "
          f"({total_rows} rows; cells by role: {cells_by_role})")
    print(f"  by audience: {by_audience}")


if __name__ == '__main__':
    main()
