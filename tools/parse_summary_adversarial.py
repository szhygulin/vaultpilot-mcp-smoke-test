#!/usr/bin/env python3
"""
Parse adversarial-mode (Pass-2 / Pass-3) transcripts -> summary.txt.

Same as parse_summary.py but additionally extracts the [ADVERSARIAL_RESULT]
block (role / attack_attempted / defense_layer_that_caught_it /
did_user_get_tricked / notes) from each transcript.

This is the structured extract the analysis subagent uses to produce
the defensive resilience matrix in Phase 5 of an adversarial run.

Usage:
  tools/parse_summary_adversarial.py                 # CWD
  tools/parse_summary_adversarial.py <workdir>       # explicit workdir
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
        for k in ('SCRIPT_ID', 'ROLE', 'ATTACK', 'CATEGORY', 'CHAIN', 'SCRIPT'):
            m = re.search(rf'^{k}:\s*(.+)$', text, re.M)
            if m:
                rec[k.lower()] = m.group(1).strip()
        # OUTCOME — optional in some adversarial transcripts
        m = re.search(r'\[OUTCOME\](.*?)(?=\[OBSERVATIONS\]|\[ADVERSARIAL_RESULT\]|\Z)', text, re.S)
        rec['outcome'] = (m.group(1).strip() if m else '').replace('\n', ' ')[:300]
        # ADVERSARIAL_RESULT block — primary signal
        m = re.search(r'\[ADVERSARIAL_RESULT\](.*?)(?=={3,}|\Z)', text, re.S)
        rec['adv'] = (m.group(1).strip() if m else '')[:1500]
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
            role = r.get('role', '?')
            o.write(f"=== {sid} | role:{role} | {r.get('category','?')} ===\n")
            if 'script' in r:
                o.write(f"SCRIPT: {r['script'][:200]}\n")
            if 'attack' in r:
                o.write(f"ATTACK: {r['attack'][:200]}\n")
            if r['outcome']:
                o.write(f"OUTCOME: {r['outcome']}\n")
            o.write(f"ADVERSARIAL_RESULT:\n{r['adv'][:1500]}\n\n")

    # Role distribution sanity check
    from collections import Counter
    roles = Counter(r.get('role', '?') for r in records)
    print(f"wrote {out_path}: {len(records)} records (role distribution: {dict(roles)})")


if __name__ == '__main__':
    main()
