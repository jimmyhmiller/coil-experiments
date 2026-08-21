#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(cd "$here/../../.." && pwd)"
out="${TMPDIR:-/tmp}/heap-inspector-demo"
cd "$root"
coil build "$here/demo.coil" -o "$out" \
  --use experiments.heap-inspector.transform
"$out"
