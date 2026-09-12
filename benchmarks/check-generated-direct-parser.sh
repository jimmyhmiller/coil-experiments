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
  word string property-name-string number spread regexp primary property object-shorthand object call member computed-member postfix expression declaration \
  return throw break continue expression-statement block if try class decorated-class class-expression class-field while do-while for-kind classic-for iterator-for for switch function function-expression statement direct-program \
  type-annotation type-alias-body implements-clause type-parameters type-alias statement-end import \
  type-template type-import type-prefix type-conditional type-arguments \
  type-arguments-before-call arrow-lookahead binding-pattern class-parameter decorated-parameter arrow jsx named-export interface \
  type-assertion \
  prefix-keyword template debugger non-null postfix-update-lookahead postfix-update optional-postfix
do
  if ! rg -Uq "\(defn\\*?[[:space:]]+parse-$production!([[:space:]]|$)" \
      "$scratch_file"; then
    printf '%s\n' "generated definition missing: parse-$production!" >&2
    exit 1
  fi
done

printf '%s\n' 'all 68 direct-parser productions are generated'
