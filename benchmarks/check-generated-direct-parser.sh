#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
coil_compiler=${COIL_COMPILER:-coil}
source_file="$project_dir/src/experiments/react-hir-frontend/direct_parser.coil"
scratch_file=$(mktemp "${TMPDIR:-/tmp}/react-hir-expanded.XXXXXX")
trap 'rm -f "$scratch_file"' EXIT INT TERM

if rg -q '^\(defn parse-' "$source_file"; then
  printf '%s\n' 'handwritten parse-* production found in direct_parser.coil' >&2
  rg -n '^\(defn parse-' "$source_file" >&2
  exit 1
fi

cd "$project_dir"
"$coil_compiler" expand "$source_file" > "$scratch_file"

for production in \
  word string primary property object-shorthand object call member computed-member postfix expression declaration \
  return expression-statement block if while function statement direct-program \
  type-annotation type-alias-body type-parameters type-alias statement-end import \
  type-arguments \
  type-arguments-before-call arrow-lookahead binding-pattern arrow jsx named-export interface \
  type-assertion \
  prefix-keyword template debugger non-null
do
  if ! rg -Uq "\(defn\\*?[[:space:]]+parse-$production!([[:space:]]|$)" \
      "$scratch_file"; then
    printf '%s\n' "generated definition missing: parse-$production!" >&2
    exit 1
  fi
done

printf '%s\n' 'all 39 direct-parser productions are generated'
