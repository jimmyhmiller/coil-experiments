#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

raylib_dir="build/c-raylib/raylib"
raylib_revision="c1ab645ca298a2801097931d1079b10ff7eb9df8"

if [ ! -d "$raylib_dir/.git" ]; then
  mkdir -p "$(dirname "$raylib_dir")"
  git clone https://github.com/raysan5/raylib.git "$raylib_dir"
fi

current_revision=$(git -C "$raylib_dir" rev-parse HEAD)
if [ "$current_revision" != "$raylib_revision" ]; then
  echo "raylib checkout is at $current_revision; expected $raylib_revision" >&2
  echo "Use a clean build/c-raylib/raylib checkout for the reproducible demo." >&2
  exit 1
fi

coil build src/apps/raylib-demo/main.coil \
  --release \
  -o build/c-raylib/raylib-reader-demo

exec build/c-raylib/raylib-reader-demo
