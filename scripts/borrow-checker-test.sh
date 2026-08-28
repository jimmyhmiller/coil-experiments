#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

coil test src/experiments/borrow-checker/borrow_checker_test.coil

demo_output=$(coil run src/experiments/borrow-checker/demo.coil)
if [ "$demo_output" != "total: 42" ]; then
  printf '%s\n' "unexpected borrow-checker demo output: $demo_output" >&2
  exit 1
fi

for case in tests/borrow-checker/borrow_then_move.coil \
            tests/borrow-checker/branch_move.coil \
            tests/borrow-checker/conflicting_borrow.coil \
            tests/borrow-checker/escape_aggregate.coil \
            tests/borrow-checker/escape_call.coil \
            tests/borrow-checker/escape_return.coil \
            tests/borrow-checker/ffi_without_unsafe.coil \
            tests/borrow-checker/loop_move.coil \
            tests/borrow-checker/move_out_of_borrow.coil \
            tests/borrow-checker/named_owned_sum_match.coil \
            tests/borrow-checker/raw_free.coil \
            tests/borrow-checker/reassign_while_borrowed.coil \
            tests/borrow-checker/use_after_move.coil; do
  log=$(mktemp)
  if coil check "$case" >"$log" 2>&1; then
    printf '%s\n' "expected rejection but check succeeded: $case" >&2
    rm -f "$log"
    exit 1
  fi
  if ! grep -E 'use of moved value|ownership .* differs|across a loop iteration|borrow-checker: (borrowed view escapes|owner is used|conflicting borrow|raw memory|bind-and-match)' "$log" >/dev/null; then
    printf '%s\n' "wrong rejection for $case" >&2
    sed -n '1,120p' "$log" >&2
    rm -f "$log"
    exit 1
  fi
  rm -f "$log"
done

coil run tests/borrow-checker/unsafe_boundary.coil >/dev/null

printf '%s\n' 'borrow-checker positive and negative tests passed'
