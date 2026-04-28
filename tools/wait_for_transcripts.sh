#!/bin/bash
#
# Block until <transcripts-dir> contains at least <count> .txt files,
# then exit. Used in background mode (run_in_background:true) by the
# parent agent so it gets a single completion notification when all
# subagent dispatches are in.
#
# Usage:
#   tools/wait_for_transcripts.sh <count>                 # default transcripts/
#   tools/wait_for_transcripts.sh <count> <dir>           # explicit dir
#   tools/wait_for_transcripts.sh <count> <dir> <pattern> # filter by glob
#
# Examples:
#   tools/wait_for_transcripts.sh 220 transcripts                 # all 220 transcripts
#   tools/wait_for_transcripts.sh 67 transcripts 'b*.txt'         # 67 b-prefixed only
#
set -euo pipefail
COUNT="${1:?usage: $0 <count> [<dir>] [<pattern>]}"
T_DIR="${2:-transcripts}"
PATTERN="${3:-*.txt}"

cd "$T_DIR" 2>/dev/null || { echo "no $T_DIR dir" >&2; exit 1; }
cd ..

count_now() {
    ls "$T_DIR"/$PATTERN 2>/dev/null | wc -l | tr -d ' '
}

start=$(date +%s)
echo "waiting for $COUNT files matching $T_DIR/$PATTERN..."
until [ "$(count_now)" -ge "$COUNT" ]; do
    sleep 10
done
elapsed=$(( $(date +%s) - start ))
echo "all $COUNT files present after ${elapsed}s"
