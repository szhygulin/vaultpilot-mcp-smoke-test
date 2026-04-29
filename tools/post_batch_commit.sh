#!/bin/bash
# tools/post_batch_commit.sh — auto-commit + push + PR for a completed smoke-test batch.
#
# Usage: tools/post_batch_commit.sh <batch_number>
#
# Effects:
#   1. Creates branch `batch-<NN>-results` (NN zero-padded; never main per CLAUDE.md).
#   2. Stages and commits runs/matrix-sampled/batch-<NN>/ + progress.json.
#   3. Pushes the branch with -u to set upstream.
#   4. Opens a PR with title + body templated from aggregate.json + findings.md.
#
# This script is idempotent in the sense that re-running on the same batch
# (already committed) will fail at `git checkout -b` and the user can resolve
# manually. We DO NOT force-push or amend — every batch gets its own branch.
#
# Exits non-zero on any error (set -e). Caller (the /run-batch slash command)
# surfaces failures to the user.

set -euo pipefail

batch="${1:-}"
if [[ -z "$batch" ]]; then
    echo "Usage: $0 <batch_number>" >&2
    exit 1
fi
pad=$(printf '%02d' "$batch")
batch_dir="runs/matrix-sampled/batch-${pad}"

if [[ ! -d "$batch_dir" ]]; then
    echo "ERROR: $batch_dir does not exist." >&2
    exit 1
fi
if [[ ! -f "$batch_dir/aggregate.json" ]]; then
    echo "ERROR: $batch_dir/aggregate.json missing — has Phase 4 mark-completed run?" >&2
    exit 1
fi
if [[ ! -f "$batch_dir/findings.md" ]]; then
    echo "ERROR: $batch_dir/findings.md missing — has Phase 5 analyst run?" >&2
    exit 1
fi
if [[ ! -f "$batch_dir/issues.md" ]]; then
    echo "ERROR: $batch_dir/issues.md missing — has Phase 6 filer run?" >&2
    exit 1
fi

# Extract headline numbers for the commit message + PR title.
total=$(jq -r '.total_transcripts' "$batch_dir/aggregate.json")
tricked=$(jq -r '.tricked_count' "$batch_dir/aggregate.json")
filed=$(grep -c '^| [0-9]' "$batch_dir/issues.md" || echo 0)
roles=$(jq -r '.by_role | to_entries | map("\(.key): \(.value)") | join(", ")' "$batch_dir/aggregate.json")

branch="batch-${pad}-results"
if git rev-parse --verify "$branch" >/dev/null 2>&1; then
    echo "ERROR: branch $branch already exists. Resolve manually." >&2
    exit 1
fi

git checkout -b "$branch"
git add "$batch_dir/" runs/matrix-sampled/progress.json

git commit -m "$(cat <<EOF
batch-${batch} results: ${total} cells, ${tricked} user-tricked, ${filed} issues filed

Roles: ${roles}

Artifacts:
- ${batch_dir}/scripts.json — dispatched cells
- ${batch_dir}/transcripts/ — per-cell reports
- ${batch_dir}/summary.txt — structured summary
- ${batch_dir}/aggregate.json — counters
- ${batch_dir}/findings.md — Phase 5 markdown analysis
- ${batch_dir}/issues.draft.json — drafted issues
- ${batch_dir}/issues.md — filing log with URLs
EOF
)"

git push -u origin "$branch"

# PR body: paste findings.md (it's the canonical analysis already).
gh pr create \
    --title "batch-${batch} results: ${total} cells, ${tricked} tricked, ${filed} issues filed" \
    --body-file "$batch_dir/findings.md"

echo "post_batch_commit.sh complete: branch=$branch"
