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

count=0
for fixture in "$benchmark_dir"/react-hir-syntax-fixtures/*.ts \
               "$benchmark_dir"/react-hir-syntax-fixtures/*.tsx; do
  [ -f "$fixture" ] || continue
  "$checker" "$fixture"
  count=$((count + 1))
done

rejected=0
for fixture in "$benchmark_dir"/react-hir-invalid-syntax-fixtures/*.ts \
               "$benchmark_dir"/react-hir-invalid-syntax-fixtures/*.tsx; do
  [ -f "$fixture" ] || continue
  set +e
  "$checker" "$fixture" >/dev/null 2>&1
  status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    printf 'invalid syntax fixture unexpectedly succeeded: %s\n' "$fixture" >&2
    exit 1
  fi
  if [ "$status" -ne 1 ]; then
    printf 'invalid syntax fixture failed unsafely (status %d): %s\n' \
      "$status" "$fixture" >&2
    exit 1
  fi
  rejected=$((rejected + 1))
done

printf 'all %d valid fixtures verified and %d invalid fixtures rejected\n' \
  "$count" "$rejected"
