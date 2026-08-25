#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(cd "$here/../../.." && pwd)"
out="${TMPDIR:-/tmp}/heap-inspector-viewer-demo"
cd "$root"
coil build "$here/viewer_demo.coil" -o "$out" --use experiments.heap-inspector.transform
exec "$out"
