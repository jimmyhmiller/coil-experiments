#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
oxc_dir=${OXC_DIR:-$HOME/Documents/Code/open-source/oxc}
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-type-oracle.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT INT TERM

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

mkdir -p "$scratch_dir/src"
cp "$benchmark_dir/typescript-type-oracle/src/main.rs" "$scratch_dir/src/main.rs"

cat > "$scratch_dir/Cargo.toml" <<EOF
[package]
name = "react-hir-typescript-type-oracle"
version = "0.1.0"
edition = "2024"
publish = false

[dependencies]
oxc_allocator = { path = "$oxc_dir/crates/oxc_allocator" }
oxc_ast = { path = "$oxc_dir/crates/oxc_ast" }
oxc_ast_visit = { path = "$oxc_dir/crates/oxc_ast_visit" }
oxc_parser = { path = "$oxc_dir/crates/oxc_parser" }
oxc_span = { path = "$oxc_dir/crates/oxc_span" }
oxc_syntax = { path = "$oxc_dir/crates/oxc_syntax" }
EOF

CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-$project_dir/target/typescript-type-oracle} \
  cargo run --release --quiet --manifest-path "$scratch_dir/Cargo.toml" -- "$checker"
