#!/usr/bin/env python3
"""
tools/prepare_dispatch.py — One-shot dispatch helper for smoke-test batch.

Replaces the ad-hoc bash loop:
  for id in $(jq -r '.scripts[].id' scripts.json); do
    python3 tools/build_dispatch_prompt.py --batch N --cell-id "$id" > /tmp/.../$id.txt
  done

Reads runs/matrix-sampled/batch-NN/scripts.json, builds the dispatch prompt
for every cell via the canonical builder (`build_dispatch_prompt.build_prompt`),
writes per-cell prompt files to /tmp/batch{NN:02d}-prompts/<id>.txt, and emits
a single JSON object to stdout for the orchestrator to consume.

Usage:
  python3 tools/prepare_dispatch.py --batch N
  python3 tools/prepare_dispatch.py --scripts <path> --batch N --output-dir <dir>

Output (stdout, JSON):
  {
    "prompts_dir": "/tmp/batch04-prompts",
    "cell_ids": ["expert-112-C.5", "expert-030-A.3", ...],
    "cell_count": 50
  }
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
from build_dispatch_prompt import build_prompt  # noqa: E402

SAMPLE_DIR = REPO_ROOT / "runs" / "matrix-sampled"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--batch", type=int, required=True,
                    help="Batch number (e.g. 4)")
    ap.add_argument("--scripts", default=None,
                    help="Override path to scripts.json (default: "
                         "REPO_ROOT/runs/matrix-sampled/batch-NN/scripts.json)")
    ap.add_argument("--output-dir", default=None,
                    help="Override prompts output dir (default: "
                         "/tmp/batch{NN:02d}-prompts)")
    args = ap.parse_args()

    if args.scripts:
        scripts_path = Path(args.scripts)
    else:
        scripts_path = SAMPLE_DIR / f"batch-{args.batch:02d}" / "scripts.json"

    if not scripts_path.exists():
        sys.exit(f"scripts.json not found: {scripts_path}")

    data = json.loads(scripts_path.read_text())
    cells = data.get("scripts", [])
    if not cells:
        sys.exit(f"no cells in {scripts_path}")

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = Path(f"/tmp/batch{args.batch:02d}-prompts")
    out_dir.mkdir(parents=True, exist_ok=True)

    cell_ids = []
    for cell in cells:
        cell_id = cell.get("id")
        if not cell_id:
            sys.exit(f"cell missing 'id' field: {cell}")
        try:
            prompt = build_prompt(cell, args.batch)
        except ValueError as e:
            sys.exit(f"build_prompt failed for {cell_id}: {e}")
        (out_dir / f"{cell_id}.txt").write_text(prompt)
        cell_ids.append(cell_id)

    out = {
        "prompts_dir": str(out_dir),
        "cell_ids": cell_ids,
        "cell_count": len(cell_ids),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
