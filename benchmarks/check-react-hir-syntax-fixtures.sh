#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

count=0
for fixture in "$benchmark_dir"/react-hir-syntax-fixtures/*.ts; do
  "$checker" "$fixture"
  count=$((count + 1))
done

printf 'all %d React HIR syntax fixtures parsed and verified\n' "$count"
