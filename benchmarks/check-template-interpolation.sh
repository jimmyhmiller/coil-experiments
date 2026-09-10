#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

result=$($checker "$benchmark_dir/fixtures/template-interpolation.ts")
printf '%s\n' "$result"
printf '%s\n' "$result" | rg -q 'references=2$'
