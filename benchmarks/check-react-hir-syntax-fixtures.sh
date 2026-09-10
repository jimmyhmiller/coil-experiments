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

rejected=0
for fixture in "$benchmark_dir"/react-hir-invalid-syntax-fixtures/*.ts; do
  if "$checker" "$fixture" >/dev/null 2>&1; then
    printf 'invalid syntax fixture unexpectedly succeeded: %s\n' "$fixture" >&2
    exit 1
  fi
  rejected=$((rejected + 1))
done

printf 'all %d valid fixtures verified and %d invalid fixtures rejected\n' \
  "$count" "$rejected"
