#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

"$checker" "$benchmark_dir/fixtures/typescript-generated-core.ts"
