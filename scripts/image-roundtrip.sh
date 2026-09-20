#!/usr/bin/env bash
# Two-process image round trip: build+save a live world in one process, load and
# verify it in a separate process. This is the honest phase-B/C gate — the
# image genuinely crosses a process boundary. Not Python; a test harness only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

coil="${COIL:-coil}"
bin="build/image-roundtrip"
img="$(mktemp -t coil-image.XXXXXX).coilimage"
trap 'rm -f "$img"' EXIT

echo "building $bin"
"$coil" build src/experiments/image/roundtrip.coil -o "$bin"

echo "process 1: save"
save_out="$("$bin" save "$img")"
echo "  $save_out"
case "$save_out" in
  SAVE-OK*) ;;
  *) echo "FAIL: save did not report SAVE-OK"; exit 1 ;;
esac

echo "process 2: load + verify"
load_out="$("$bin" load "$img")"
echo "  $load_out"
case "$load_out" in
  "LOAD-OK v1=10 v2=20 tags1=abcde tags2=bcd ledger=2") ;;
  *) echo "FAIL: load did not verify"; exit 1 ;;
esac

echo "PASS: image round trip across two processes"
