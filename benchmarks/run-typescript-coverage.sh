#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
oxc_dir=${OXC_DIR:-$HOME/Documents/Code/open-source/oxc}
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-typescript-coverage.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT INT TERM

if [ "$#" -eq 0 ]; then
  echo "usage: $0 TYPESCRIPT_OR_TSX_PATH..." >&2
  exit 64
fi

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

mkdir -p "$scratch_dir/src"
cp "$benchmark_dir/typescript-coverage/src/main.rs" "$scratch_dir/src/main.rs"

cat > "$scratch_dir/Cargo.toml" <<EOF
[package]
name = "react-hir-typescript-coverage"
version = "0.1.0"
edition = "2024"
publish = false

[dependencies]
oxc_allocator = { path = "$oxc_dir/crates/oxc_allocator" }
oxc_parser = { path = "$oxc_dir/crates/oxc_parser" }
oxc_span = { path = "$oxc_dir/crates/oxc_span" }
EOF

CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-$project_dir/target/typescript-coverage} \
  cargo run --release --quiet --manifest-path "$scratch_dir/Cargo.toml" -- \
  "$checker" "$@"
