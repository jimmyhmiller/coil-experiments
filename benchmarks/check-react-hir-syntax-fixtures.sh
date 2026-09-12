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

# Escaped and raw spellings are one ECMAScript identifier identity. Acceptance
# alone would not catch a parser that created unresolved references for the
# escaped spellings, so pin the binding links in the verified textual IR.
escaped_ir=$(mktemp "${TMPDIR:-/tmp}/react-hir-escaped-identifiers.XXXXXX")
trap 'rm -f "$escaped_ir"' EXIT HUP INT TERM
"$checker" "$benchmark_dir/react-hir-syntax-fixtures/escaped-identifiers.ts" \
  --dump-ir >"$escaped_ir"
for expected in \
  'reference 0 binding(0)' \
  'reference 1 binding(0)' \
  'reference 2 binding(2)'; do
  if ! grep -F "$expected" "$escaped_ir" >/dev/null; then
    printf 'escaped identifier lost canonical binding identity: %s\n' "$expected" >&2
    exit 1
  fi
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
