#!/usr/bin/env python3
"""
tools/file_batch_issues.py — File a batch's issue drafts as GitHub issues.

Reads `runs/matrix-sampled/batch-NN/issues.draft.json` (produced by the
Phase 3.6 / Phase 5 analysis subagent), files each as a GitHub issue via
`gh issue create`, and records the resulting URLs in
`runs/matrix-sampled/batch-NN/issues.md`.

Usage:
  python3 tools/file_batch_issues.py --batch N --repo owner/repo
  python3 tools/file_batch_issues.py --batch N --repo owner/repo --dry-run
  python3 tools/file_batch_issues.py --batch N --repo owner/repo --only 1,3,7

Input schema (`issues.draft.json`):
{
  "batch": 1,
  "source_attribution": "Smoke-test batch-1 ... <free-form>",   # optional
  "issues": [
    {
      "title": "<≤120 chars>",
      "labels": ["security_finding", "tool_gap"],
      "summary": "1-2 paragraphs of context",
      "repro": "scripts X, Y, Z (free-form)",
      "suggested_fix": "concrete API/behavior change",
      "extra_sections": {                                       # optional
        "Structural risk": "..."
      }
    }
  ]
}

Each filed issue body is assembled in the Phase 6 template:
  ## Summary
  ## Repro
  ## Suggested fix
  [## Structural risk]   (if extra_sections.Structural risk)
  ## Source
  Smoke-test reference + 🤖 Generated with attribution.

Idempotency:
- The script appends to `issues.md` rather than rewriting, so re-running
  with `--only` is safe.
- Pass `--dry-run` to print the planned `gh issue create` calls without
  executing them.

Pre-reqs:
- `gh auth status` clean
- Labels referenced in `issues.draft.json` must exist on the repo (or be
  pre-created via `gh label create`); the script does not auto-create.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "runs" / "matrix-sampled"


def _batch_dir(batch_n: int) -> Path:
    return SAMPLE_DIR / f"batch-{batch_n:02d}"


def _format_body(issue: dict, batch_n: int, source_attribution: str | None) -> str:
    parts = ["## Summary\n", issue["summary"].strip(), "\n\n"]
    parts += ["## Repro\n", issue.get("repro", "").strip() or "(none)", "\n\n"]
    parts += ["## Suggested fix\n", issue.get("suggested_fix", "").strip() or "(none)", "\n\n"]
    for header, body in (issue.get("extra_sections") or {}).items():
        parts += [f"## {header}\n", body.strip(), "\n\n"]
    parts += ["## Source\n"]
    if source_attribution:
        parts += [source_attribution.strip(), "\n\n"]
    else:
        parts += [
            f"Smoke-test batch-{batch_n} (matrix-sampled adversarial run). "
            f"Findings: `runs/matrix-sampled/batch-{batch_n:02d}/findings.md`.\n\n"
        ]
    parts += ["🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"]
    return "".join(parts)


def _file_one(issue: dict, body: str, repo: str, dry_run: bool) -> str:
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", issue["title"],
        "--body", body,
    ]
    for label in issue.get("labels", []):
        cmd.extend(["--label", label])
    if dry_run:
        print(f"  [dry-run] {' '.join(repr(c) for c in cmd[:5])} ... "
              f"(+{len(issue.get('labels', []))} labels)")
        return f"DRY-RUN-{issue['title'][:40]}"
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ FAILED: {result.stderr.strip()}", file=sys.stderr)
        return f"FAILED — {result.stderr.strip()[:120]}"
    return result.stdout.strip()


def _append_to_issues_md(batch_n: int, urls: list[tuple]) -> None:
    """Append the filed-issue table to runs/matrix-sampled/batch-NN/issues.md."""
    md_path = _batch_dir(batch_n) / "issues.md"
    fresh = not md_path.exists()
    with md_path.open("a") as f:
        if fresh:
            f.write(f"# Batch-{batch_n} — issues filed\n\n")
            f.write("| # | Issue | Labels | Title |\n|---|---|---|---|\n")
        for idx, title, url, labels in urls:
            labels_md = ", ".join(f"`{l}`" for l in labels) if labels else "—"
            f.write(f"| {idx} | {url} | {labels_md} | {title} |\n")
    print(f"\nAppended {len(urls)} entries to {md_path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--batch", type=int, required=True,
                    help="Batch number (e.g. 1)")
    ap.add_argument("--repo", required=True,
                    help="Target repo as owner/name (e.g. szhygulin/vaultpilot-mcp)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned gh calls, don't execute")
    ap.add_argument("--only", default=None,
                    help="Comma-separated 1-based indices to file (e.g. '1,3,5'); "
                         "default: all")
    args = ap.parse_args()

    draft_path = _batch_dir(args.batch) / "issues.draft.json"
    if not draft_path.exists():
        sys.exit(f"draft not found: {draft_path}\n"
                 f"the analysis subagent must produce this file as part of "
                 f"Phase 3.6 (per CLAUDE.md Smoke-test methodology section)")

    draft = json.loads(draft_path.read_text())
    issues = draft.get("issues", [])
    if not issues:
        sys.exit("no issues in draft")

    only_set = None
    if args.only:
        only_set = {int(x.strip()) for x in args.only.split(",") if x.strip()}

    print(f"Filing {sum(1 for i in range(len(issues)) if not only_set or (i+1) in only_set)} "
          f"of {len(issues)} draft issues against {args.repo}"
          f"{' (DRY-RUN)' if args.dry_run else ''}\n")

    urls = []
    for i, issue in enumerate(issues, start=1):
        if only_set and i not in only_set:
            continue
        body = _format_body(issue, args.batch, draft.get("source_attribution"))
        print(f"[{i}/{len(issues)}] {issue['title'][:80]}")
        url = _file_one(issue, body, args.repo, args.dry_run)
        if url and not url.startswith("FAILED"):
            print(f"  ✓ {url}")
        urls.append((i, issue["title"], url, issue.get("labels", [])))

    print("\n=== Summary ===")
    for i, title, url, labels in urls:
        labels_str = ",".join(labels) if labels else "—"
        print(f"  #{i}  {url}  [{labels_str}]  {title[:80]}")

    if not args.dry_run:
        _append_to_issues_md(args.batch, urls)


if __name__ == "__main__":
    main()
