#!/usr/bin/env bash
# Full-boot gate across two processes, through the real JIT controller:
#   save    build a live world, mutate it at runtime, save
#   boot    fresh process: replay the ledger (code) + overlay heap state
#   upgrade fresh process: boot, then a schema upgrade migrates state forward
# Not Python; a test harness only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
coil="${COIL:-coil}"
bin="build/image-boot-demo"
img="$(mktemp -t coil-boot.XXXXXX).coilimage"
trap 'rm -f "$img"' EXIT

echo "building $bin"
"$coil" build src/experiments/image/boot_demo.coil -o "$bin"

check() { # label expected actual
  echo "  $3"
  if [ "$3" != "$2" ]; then echo "FAIL($1): expected [$2]"; exit 1; fi
}

echo "process 1: save (build via controller, mutate, save)"
check save "SAVE-OK a=99 b=2 ledger=1" "$("$bin" save "$img")"

echo "process 2: boot (replay code + overlay state)"
check boot "BOOT-OK a=99 b=2 ledger=1" "$("$bin" boot "$img")"

echo "process 3: upgrade (boot, then migrate schema forward)"
check upgrade "UPGRADE-OK a=99 b=2 c=42" "$("$bin" upgrade "$img")"

echo "PASS: full image boot + upgrade across processes"
