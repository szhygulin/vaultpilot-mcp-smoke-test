#!/bin/bash
#
# Concatenate per-script transcripts into a single corpus file.
#
# Used between Phase 4 and Phase 5 of the smoke-test methodology
# (see ../skill/SKILL.md). The concatenated file is the immutable
# corpus the analysis subagent reads (selectively, NOT into the
# parent agent's context).
#
# Usage:
#   tools/concat_transcripts.sh                        # CWD/transcripts/*.txt -> CWD/all_transcripts.txt
#   tools/concat_transcripts.sh <workdir>              # <workdir>/transcripts/*.txt -> <workdir>/all_transcripts.txt
#   tools/concat_transcripts.sh <workdir> <out-name>   # custom output name (e.g. all_transcripts_full.txt)
#
set -euo pipefail
WORKDIR="${1:-.}"
OUT_NAME="${2:-all_transcripts.txt}"

cd "$WORKDIR"
[ -d transcripts ] || { echo "no transcripts/ dir under $WORKDIR" >&2; exit 1; }

{
  for f in transcripts/*.txt; do
    echo "================================================================"
    echo "FILE: $f"
    echo "================================================================"
    cat "$f"
    echo
  done
} > "$OUT_NAME"

n=$(ls transcripts/*.txt | wc -l | tr -d ' ')
size=$(du -h "$OUT_NAME" | cut -f1)
lines=$(wc -l < "$OUT_NAME" | tr -d ' ')
echo "wrote $WORKDIR/$OUT_NAME from $n transcripts ($lines lines, $size)"
