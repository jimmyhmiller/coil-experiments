#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/jsir-differential.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT INT TERM

coil_compiler=${COIL_COMPILER:-coil}
jsir_dir=${JSIR_RS_DIR:-$HOME/Documents/Code/open-source/jsir-rs/.worktrees/coil-differential}
fixture='let x = 3; while (x) { x = x - 1; } foo(x);'

"$coil_compiler" build "$benchmark_dir/jsir-differential-coil.coil" --release \
  -o "$scratch_dir/coil-signature"
coil_signature=$(cd "$project_dir" && "$scratch_dir/coil-signature")
jsir_signature=$(printf '%s' "$fixture" | \
  cargo run --release -q --manifest-path "$jsir_dir/Cargo.toml" \
    -p jsir-swc --example coil_signature)

if [ "$coil_signature" != "$jsir_signature" ]; then
  printf '%s\n' "Coil: $coil_signature" "JSIR: $jsir_signature" >&2
  exit 1
fi

printf '%s\n' "$coil_signature"
