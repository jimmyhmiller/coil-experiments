#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
oxc_dir=${OXC_DIR:-$HOME/Documents/Code/open-source/oxc}
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-oxc.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT INT TERM

mkdir -p "$scratch_dir/src"
cp "$benchmark_dir/oxc-parser-benchmark/src/main.rs" "$scratch_dir/src/main.rs"

cat > "$scratch_dir/Cargo.toml" <<EOF
[package]
name = "react-hir-oxc-parser-benchmark"
version = "0.1.0"
edition = "2024"
publish = false

[dependencies]
oxc_allocator = { path = "$oxc_dir/crates/oxc_allocator" }
oxc_parser = { path = "$oxc_dir/crates/oxc_parser" }
oxc_span = { path = "$oxc_dir/crates/oxc_span" }
EOF

CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-$project_dir/target/oxc-parser-benchmark} \
  cargo run --release --quiet --manifest-path "$scratch_dir/Cargo.toml"
