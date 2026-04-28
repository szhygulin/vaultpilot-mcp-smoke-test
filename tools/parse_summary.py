#!/usr/bin/env python3
"""
Parse honest-mode (Pass-1) transcripts -> summary.txt.

Extracts SCRIPT_ID / CATEGORY / CHAIN / SCRIPT / OUTCOME / OBSERVATIONS
from each <workdir>/transcripts/NNN.txt and writes a flat human-readable
summary to <workdir>/summary.txt.

This is the structured per-script extract handed to the analysis
subagent in Phase 5 of the methodology. Much smaller than the full
corpus (~1-3% the size), comfortably feedable to one subagent.

Usage:
  tools/parse_summary.py                # CWD
  tools/parse_summary.py <workdir>      # explicit workdir

For adversarial-mode runs (Pass 2 / Pass 3) use parse_summary_adversarial.py
instead — it additionally extracts the [ADVERSARIAL_RESULT] block.
"""
import os, re, sys, argparse


def parse(workdir: str) -> list[dict]:
    t_dir = os.path.join(workdir, 'transcripts')
    if not os.path.isdir(t_dir):
        sys.exit(f"no transcripts/ dir under {workdir}")
    records = []
    for fn in sorted(os.listdir(t_dir)):
        if not fn.endswith('.txt'):
            continue
        text = open(os.path.join(t_dir, fn)).read()
        rec = {'file': fn}
        for k in ('SCRIPT_ID', 'CATEGORY', 'CHAIN', 'SCRIPT'):
            m = re.search(rf'^{k}:\s*(.+)$', text, re.M)
            if m:
                rec[k.lower()] = m.group(1).strip()
        m = re.search(r'\[OUTCOME\](.*?)(?=\[OBSERVATIONS\]|\[ADV|\Z)', text, re.S)
        rec['outcome'] = (m.group(1).strip() if m else '').replace('\n', ' ')[:300]
        m = re.search(r'\[OBSERVATIONS\](.*?)(?=={3,}|\[ADV|\Z)', text, re.S)
        rec['obs'] = m.group(1).strip() if m else ''
        records.append(rec)
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('workdir', nargs='?', default='.', help='workdir containing transcripts/')
    ap.add_argument('-o', '--out', default=None, help='output path (default: <workdir>/summary.txt)')
    args = ap.parse_args()

    records = parse(args.workdir)
    out_path = args.out or os.path.join(args.workdir, 'summary.txt')

    with open(out_path, 'w') as o:
        for r in records:
            sid = r.get('script_id', r['file'].replace('.txt', ''))
            o.write(f"=== {sid} | {r.get('category','?')} | {r.get('chain','?')} ===\n")
            if 'script' in r:
                o.write(f"SCRIPT: {r['script'][:200]}\n")
            o.write(f"OUTCOME: {r['outcome']}\n")
            o.write(f"OBSERVATIONS:\n{r['obs'][:1500]}\n\n")

    print(f"wrote {out_path}: {len(records)} records")


if __name__ == '__main__':
    main()
