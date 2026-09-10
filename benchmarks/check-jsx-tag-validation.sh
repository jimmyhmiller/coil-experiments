#!/bin/sh
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
checker=${REACT_HIR_CHECKER:-$project_dir/target/react-hir-check}

if [ ! -x "$checker" ]; then
  "$benchmark_dir/build-react-hir-check.sh" "$checker"
fi

if "$checker" "$benchmark_dir/fixtures/jsx-mismatched-close.tsx" >/dev/null 2>&1; then
  printf '%s\n' 'mismatched JSX closing tag was incorrectly accepted' >&2
  exit 1
fi

printf '%s\n' 'mismatched JSX closing tag rejected'
