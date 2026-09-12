#!/bin/sh
# The grammar's production shapes must determine the generated parser.
#
# Each case edits one production in frontend_spec.coil, rebuilds, and asserts
# the parser followed. A generator that indexed fixed step positions instead of
# walking the shape would pass none of these: it would either ignore the edit or
# silently emit a parser that accepts neither the old nor the new language.
set -eu

benchmark_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$benchmark_dir")
spec=$project_dir/src/experiments/react-hir-frontend/frontend_spec.coil
work=$(mktemp -d "${TMPDIR:-/tmp}/react-hir-grammar-authority.XXXXXX")
cp "$spec" "$work/spec.orig"
trap 'cp "$work/spec.orig" "$spec"; rm -rf "$work"' EXIT HUP INT TERM

fail() { printf 'grammar authority: %s\n' "$1" >&2; exit 1; }

build() {
  "$benchmark_dir/build-react-hir-check.sh" "$work/check" >/dev/null 2>"$work/build.err" \
    || return 1
  return 0
}

# 1. Removing the condition delimiters from while-production must produce a
#    parser for the undelimited form, with the loop CFG intact.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (while-production
       [(keyword "while") (terminal lparen) (rule expression) (terminal rparen)
        (rule statement)])"""
new = """     (while-production
       [(keyword "while") (rule expression) (rule statement)])"""
assert old in s, "while-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
build || fail "undelimited while-production failed to build"
printf 'let i = 0;\nwhile i < 3 { i = i + 1; }\n' >"$work/undelimited.js"
"$work/check" "$work/undelimited.js" --dump-ir >"$work/undelimited.ir" 2>&1 \
  || fail "undelimited while did not parse"
grep -q 'cf.cond_br' "$work/undelimited.ir" \
  || fail "undelimited while produced no conditional branch"
grep -c 'cf.br' "$work/undelimited.ir" >/dev/null \
  || fail "undelimited while produced no loop backedge"
cp "$work/spec.orig" "$spec"

# 2. Renaming a clause keyword must move with the grammar.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (else-clause-production
       [(keyword "else") (rule statement)])"""
new = """     (else-clause-production
       [(keyword "otherwise") (rule statement)])"""
assert old in s, "else-clause-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
build || fail "renamed else keyword failed to build"
printf 'let y = 0;\nif (y > 1) { y = 2; } otherwise { y = 3; }\n' >"$work/renamed.js"
"$work/check" "$work/renamed.js" --dump-ir >"$work/renamed.ir" 2>&1 \
  || fail "renamed else clause did not parse"
grep -q 'cf.cond_br' "$work/renamed.ir" \
  || fail "renamed else clause produced no diamond"
cp "$work/spec.orig" "$spec"

# 3. A production that no longer supplies a role a strategy needs must be a hard
#    expansion error, never a silently broken parser.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (while-production
       [(keyword "while") (terminal lparen) (rule expression) (terminal rparen)
        (rule statement)])"""
new = """     (while-production
       [(keyword "while") (terminal lparen) (rule expression) (terminal rparen)])"""
assert old in s, "while-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
if build; then fail "while-production without a body rule built successfully"; fi
grep -q 'no (rule ...) step for role: body' "$work/build.err" \
  || fail "missing body role did not report the expected error"
cp "$work/spec.orig" "$spec"

# 4. A post-test loop's leading keyword, its trailing keyword, and its ASI
#    terminator all come from the grammar.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (do-while-production
       [(keyword "do") (rule statement) (keyword "while") (terminal lparen)
        (rule expression) (terminal rparen) (terminator semicolon)])"""
new = """     (do-while-production
       [(keyword "repeat") (rule statement) (keyword "until") (terminal lparen)
        (rule expression) (terminal rparen) (terminator semicolon)])"""
assert old in s, "do-while-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
build || fail "renamed do/while keywords failed to build"
printf 'let n = 0;\nrepeat { n = n + 1; } until (n < 3);\n' >"$work/renamed-loop.js"
"$work/check" "$work/renamed-loop.js" --dump-ir >"$work/renamed-loop.ir" 2>&1 \
  || fail "renamed do/while did not parse"
grep -q 'cf.cond_br' "$work/renamed-loop.ir" \
  || fail "renamed do/while produced no conditional branch"
cp "$work/spec.orig" "$spec"

# 5. try/catch spelling and the catch binding's delimiters come from the try and
#    catch-clause productions, including the optional-binding form.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (try-production
       [(keyword "try") (rule block)])"""
new = """     (try-production
       [(keyword "attempt") (rule block)])"""
assert old in s, "try-production not found in expected form"
s = s.replace(old, new, 1)
old = """       [(keyword "catch") (terminal lparen) (rule binding) (terminal rparen)"""
new = """       [(keyword "rescue") (terminal lbracket) (rule binding) (terminal rbracket)"""
assert old in s, "catch-clause-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
build || fail "renamed try/catch clauses failed to build"
printf 'attempt {\n  work();\n} rescue [failure] {\n  handle(failure);\n}\nattempt {\n  work();\n} finally {\n  done();\n}\n' \
  >"$work/renamed-try.js"
"$work/check" "$work/renamed-try.js" --dump-ir >"$work/renamed-try.ir" 2>&1 \
  || fail "renamed try/catch did not parse"
grep -q 'js.try' "$work/renamed-try.ir" \
  || fail "renamed try/catch produced no try operation"
printf 'try {\n  work();\n} catch (e) {\n  handle(e);\n}\n' >"$work/original-try.js"
if "$work/check" "$work/original-try.js" >/dev/null 2>&1; then
  fail "the original try/catch spelling still parsed after the grammar was renamed"
fi
cp "$work/spec.orig" "$spec"

# 6. The TypeScript type-annotation colon lives in one production. Six sites
#    used to carry their own copy of it, so re-spelling it here must move all of
#    them together - parameters, return types, bindings and arrows - including
#    the lookaheads that decide whether an annotation is present at all.
#    The replacement byte must not also be a binary operator, or the test says
#    nothing: `a % number` is ambiguous with modulo, `a ~ number` is not.
python3 - "$spec" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """     (type-annotation-production
       [(terminal colon) (rule type)])"""
new = """     (type-annotation-production
       [(terminal tilde) (rule type)])"""
assert old in s, "type-annotation-production not found in expected form"
open(p, "w").write(s.replace(old, new, 1))
PY
build || fail "re-spelled type annotation failed to build"
printf 'function f(a ~ number) ~ number { return a; }\nconst x ~ number = 1;\nconst g = (p ~ number) ~ number => p;\n' \
  >"$work/annotated.ts"
"$work/check" "$work/annotated.ts" >"$work/annotated.out" 2>&1 \
  || fail "re-spelled type annotations did not parse"
printf 'function f(a: number): number { return a; }\n' >"$work/old-annotated.ts"
if "$work/check" "$work/old-annotated.ts" >/dev/null 2>&1; then
  fail "colon annotation still accepted after the grammar re-spelled it"
fi
cp "$work/spec.orig" "$spec"

printf 'grammar shapes are authoritative: 6 perturbations followed the grammar\n'
