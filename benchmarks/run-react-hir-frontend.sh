#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-benchmark.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT INT TERM

coil_compiler=${COIL_COMPILER:-coil}
c_compiler=${CC:-clang}

"$c_compiler" -O3 -c "$benchmark_dir/benchmark_barrier.c" \
  -o "$scratch_dir/benchmark_barrier.o"
"$coil_compiler" build "$benchmark_dir/react-hir-frontend.coil" --release \
  --link-flag "$scratch_dir/benchmark_barrier.o" \
  -o "$scratch_dir/react-hir-frontend-benchmark"

cd "$project_dir"
"$scratch_dir/react-hir-frontend-benchmark" "$@"
