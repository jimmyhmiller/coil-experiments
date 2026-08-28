#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

coil test src/experiments/borrow-checker/borrow_checker_test.coil

for case in tests/borrow-checker/*.coil; do
  log=$(mktemp)
  if coil check "$case" >"$log" 2>&1; then
    printf '%s\n' "expected rejection but check succeeded: $case" >&2
    rm -f "$log"
    exit 1
  fi
  if ! grep -E 'use of moved value|ownership .* differs|across a loop iteration' "$log" >/dev/null; then
    printf '%s\n' "wrong rejection for $case" >&2
    sed -n '1,120p' "$log" >&2
    rm -f "$log"
    exit 1
  fi
  rm -f "$log"
done

printf '%s\n' 'borrow-checker positive and negative tests passed'
