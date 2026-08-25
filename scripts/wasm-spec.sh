#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pin=$(tr -d '[:space:]' < "$root/tests/wasm/SPEC_REVISION")
wabt_pin=$(tr -d '[:space:]' < "$root/tests/wasm/WABT_REVISION")
cache="$root/tests/wasm/.spec-cache"
spec="$cache/spec-mvp"
wabt="$cache/wabt-mvp"
prepared="$cache/prepared-$pin"

fetch_suite() {
  mkdir -p "$cache"
  if [ ! -d "$spec/.git" ]; then
    git init -q "$spec"
    git -C "$spec" remote add origin https://github.com/WebAssembly/spec.git
  fi
  if ! git -C "$spec" cat-file -e "$pin^{commit}" 2>/dev/null; then
    git -C "$spec" fetch --depth 1 origin "$pin"
  fi
  git -C "$spec" checkout -q --detach "$pin"
  actual=$(git -C "$spec" rev-parse HEAD)
  if [ "$actual" != "$pin" ]; then
    echo "error: expected spec revision $pin, got $actual" >&2
    exit 1
  fi
}

fetch_wabt() {
  mkdir -p "$cache"
  if [ ! -d "$wabt/.git" ]; then
    git init -q "$wabt"
    git -C "$wabt" remote add origin https://github.com/WebAssembly/wabt.git
  fi
  if ! git -C "$wabt" cat-file -e "$wabt_pin^{commit}" 2>/dev/null; then
    git -C "$wabt" fetch --depth 1 origin "$wabt_pin"
  fi
  git -C "$wabt" checkout -q --detach "$wabt_pin"
  if [ ! -x "$wabt/build/wast2json" ]; then
    command -v cmake >/dev/null 2>&1 || {
      echo "error: cmake is required to build the pinned WAST converter" >&2
      exit 1
    }
    cmake -S "$wabt" -B "$wabt/build" -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    cmake --build "$wabt/build" --target wast2json -j 4
  fi
}

prepare_suite() {
  fetch_suite
  fetch_wabt
  mkdir -p "$prepared"
  for wast in "$spec"/test/core/*.wast; do
    name=$(basename "$wast" .wast)
    mkdir -p "$prepared/$name"
    "$wabt/build/wast2json" "$wast" -o "$prepared/$name/script.json"
  done
}

inventory() {
  fetch_suite
  count=$(find "$spec/test/core" -maxdepth 1 -name '*.wast' | wc -l | tr -d '[:space:]')
  echo "revision=$pin"
  echo "wast_files=$count"
  find "$spec/test/core" -maxdepth 1 -name '*.wast' -exec basename {} \; | LC_ALL=C sort
}

case "${1:-inventory}" in
  fetch) fetch_suite ;;
  fetch-wabt) fetch_wabt ;;
  prepare) prepare_suite ;;
  inventory) inventory ;;
  *)
    echo "usage: scripts/wasm-spec.sh [fetch|fetch-wabt|prepare|inventory]" >&2
    exit 2
    ;;
esac
