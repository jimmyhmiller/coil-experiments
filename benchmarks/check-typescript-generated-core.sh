#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
if [ -n "${REACT_HIR_CHECKER:-}" ]; then
  checker=$REACT_HIR_CHECKER
else
  checker=$project_dir/target/react-hir-check
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

"$checker" "$benchmark_dir/fixtures/typescript-generated-core.ts"
REACT_HIR_CHECKER="$checker" "$benchmark_dir/check-typescript-type-oracle.sh"
