#!/usr/bin/env bash
# Full-boot gate across two processes, through the real JIT controller:
#   save    build a live world, mutate it at runtime, save
#   boot    fresh process: replay the ledger (code) + overlay heap state
#   upgrade fresh process: boot, then a schema upgrade migrates state forward
#
# The JIT host (which embeds Coil's in-process compiler) is built ONCE into a
# static archive and linked; rebuilding it on every app build cost ~37 s, while
# linking the prebuilt archive costs under a second.
# Not Python; a test harness only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
coil="${COIL:-coil}"
lib="build/libcoilimage.a"
bin="build/image-boot-demo"
img="$(mktemp -t coil-boot.XXXXXX).coilimage"
trap 'rm -f "$img"' EXIT

# Rebuild the JIT host only when the image/live layer it wraps has changed.
stale=0
if [ ! -f "$lib" ]; then
  stale=1
else
  while IFS= read -r src; do
    [ "$src" -nt "$lib" ] && stale=1 && break
  done < <(ls src/experiments/image/*.coil src/experiments/heap-inspector/*.coil 2>/dev/null)
fi

if [ "$stale" = "1" ]; then
  echo "building the JIT host archive (once; it embeds the compiler)"
  "$coil" build src/experiments/image/jit_host.coil --lib -o "$lib"
else
  echo "reusing $lib"
fi

echo "building $bin (links the prebuilt archive)"
"$coil" build src/experiments/image/boot_demo.coil -o "$bin" --link-flag "$root/$lib"

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
