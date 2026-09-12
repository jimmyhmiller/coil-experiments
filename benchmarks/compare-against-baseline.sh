#!/bin/sh
# Prove a refactor changed no observable behaviour, and did not cost throughput.
#
# Builds the checker from a baseline git ref in a scratch worktree, then compares
# it against the working tree across every syntax fixture:
#
#   1. textual IR must be byte-identical for every valid fixture
#   2. every invalid fixture must still be rejected, with the same diagnostic
#   3. end-to-end text-to-SSA throughput is reported for both
#
# Usage: benchmarks/compare-against-baseline.sh [BASELINE_REF]   (default: main)
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
baseline_ref=${1:-main}

work=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-baseline.XXXXXX")
tree=$work/tree
cleanup() {
  git -C "$project_dir" worktree remove --force "$tree" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT HUP INT TERM

printf 'building baseline (%s)...\n' "$baseline_ref"
git -C "$project_dir" worktree add --detach "$tree" "$baseline_ref" >/dev/null 2>&1
"$tree/benchmarks/build-react-hir-check.sh" "$work/check-baseline" >/dev/null

printf 'building working tree...\n'
"$benchmark_dir/build-react-hir-check.sh" "$work/check-current" >/dev/null

differences=0
compared=0
for fixture in "$benchmark_dir"/react-hir-syntax-fixtures/*.ts \
               "$benchmark_dir"/react-hir-syntax-fixtures/*.tsx; do
  [ -f "$fixture" ] || continue
  compared=$((compared + 1))
  "$work/check-baseline" "$fixture" --dump-ir >"$work/a.ir" 2>&1 || true
  "$work/check-current"  "$fixture" --dump-ir >"$work/b.ir" 2>&1 || true
  if ! cmp -s "$work/a.ir" "$work/b.ir"; then
    differences=$((differences + 1))
    printf 'IR CHANGED: %s\n' "${fixture##*/}"
    diff "$work/a.ir" "$work/b.ir" | head -20
  fi
done

rejected_differences=0
rejected=0
for fixture in "$benchmark_dir"/react-hir-invalid-syntax-fixtures/*.ts \
               "$benchmark_dir"/react-hir-invalid-syntax-fixtures/*.tsx; do
  [ -f "$fixture" ] || continue
  rejected=$((rejected + 1))
  a=$("$work/check-baseline" "$fixture" 2>&1 || true)
  b=$("$work/check-current"  "$fixture" 2>&1 || true)
  if [ "$a" != "$b" ]; then
    rejected_differences=$((rejected_differences + 1))
    printf 'DIAGNOSTIC CHANGED: %s\n  baseline: %s\n  current:  %s\n' \
      "${fixture##*/}" "$a" "$b"
  fi
done

printf '\n%d valid fixtures compared, %d with changed IR\n' "$compared" "$differences"
printf '%d invalid fixtures compared, %d with changed diagnostics\n' \
  "$rejected" "$rejected_differences"

if [ "$differences" -ne 0 ] || [ "$rejected_differences" -ne 0 ]; then
  printf '\nbehaviour changed against %s\n' "$baseline_ref" >&2
  exit 1
fi

printf '\nbehaviour identical to %s. throughput:\n\n' "$baseline_ref"
printf '  baseline: '
( cd "$tree" && COIL_COMPILER=${COIL_COMPILER:-coil} \
    benchmarks/run-react-hir-direct-large.sh 2>/dev/null | tail -3 ) || \
  printf '(benchmark unavailable at baseline)\n'
printf '  current:  '
( cd "$project_dir" && COIL_COMPILER=${COIL_COMPILER:-coil} \
    benchmarks/run-react-hir-direct-large.sh 2>/dev/null | tail -3 ) || \
  printf '(benchmark unavailable)\n'
