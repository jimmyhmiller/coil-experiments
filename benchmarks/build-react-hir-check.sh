#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
coil_compiler=${COIL_COMPILER:-coil}
output=${1:-$project_dir/target/react-hir-check}

mkdir -p "$(dirname -- "$output")"
"$coil_compiler" build "$benchmark_dir/react-hir-check.coil" --release -o "$output"
