# Ohm compatibility status

The compatibility target is the official `ohmjs/ohm` test suite at upstream
revision `43c345b920c98b3eb13ce6b12df2b6ebd400b63b`.

This is a behavior report, not a claim that reading the bootstrap grammar alone
constitutes compatibility.

## Current passing layer

The generated Coil parser currently supports and tests:

- UTF-8 terminals and Unicode-scalar ranges, including supplementary-plane
  code points;
- sequence and ordered choice;
- `*`, `+`, and `?`;
- negative and positive lookahead;
- syntactic and lexical space behavior;
- `letter`, `lower`, `upper`, `unicodeLtmo`, `digit`, `alnum`, and `hexDigit`
  built-ins, with deterministic Unicode 17 category matching for the letter
  classes and every public `UnicodeChar` recipe category/property;
- locale-invariant `caseInsensitive` terminals, including Ohm's dotted-I,
  dotless-I, umlaut, and eszett edge cases;
- `applySyntactic`, including lexical-context validation, syntactic space
  skipping, trailing-space consumption, parameterized applications, and its
  CST wrapper;
- `any` and `end`;
- `ExperimentalIndentationSensitive`, including pinned `findIndentation`
  virtual-token placement, zero-width `indent`/`dedent` CST bindings,
  terminal barriers, `any` consumption, mandatory final dedents,
transactional backtracking, trace intervals, and rejection of incremental
  edits after a matcher has produced a result, plus upstream's skipped nested
  dedent regression `#467`;
- rule applications;
- parameterized rules, including multiple and complex arguments, repetition,
  and inline cases;
- direct, indirect, nested, nested-indirect, and multiple-head left recursion,
  with memoized CST seed growth;
- chained grammar inheritance, inherited default-rule order, overrides,
  extensions, built-in overrides/extensions, and ordered `...` super-splice;
- grammar-construction validation for duplicate formals, wrong argument counts,
  non-arity-one arguments, and undeclared rule applications;
- terminal nodes, built-in-rule nodes, iteration nodes, and inline case nodes;
- Ohm 17 binding arity, including column-transposed `_iter` nodes for
  multi-binding `*`, `+`, and `?` operands and optional-node metadata;
- construction-time rejection of alternatives with inconsistent binding
  arity, including Ohm's predicate, lexicalization, inline-case, and inherited
  super-splice rules;
- construction-time rejection of statically nullable `*` and `+` operands,
  plus runtime zero-width detection for parameter-dependent operands, including
  the official nested `ListOf<"a"?, "">` case, with owning grammar-source
  excerpts and the most-recent-last application stack;
- rightmost failure positions, typed/deduplicated expected-input aggregation,
  negative-predicate suppression and display strings, described-rule failures,
  memoized failure replay, fluffy/non-fluffy subsumption, UTF-16 line/column
  coordinates, Ohm-style short and contextual failure messages, and retained
  rightmost-failure inspection (`match-failure-*`);
- the grammar syntax needed to read canonical `ohm-grammar.ohm`.
- Coil-native `InputStream` UTF-16 code-unit/code-point reads, examined-length
  behavior, string matching, JavaScript-style slicing (including exact
  lone-surrogate slices), and immutable `Interval` values,
  including collapse, arbitrary-list coverage, source-identity mismatch
  detection, `minus`, `relativeTo`, `trimmed`, `subInterval`, and exact
  line/column rendering with clipped, overlapping, cross-line, CRLF, and
  multi-digit-line-number ranges. Optional previous/next-line accessors retain
  Ohm's distinction between `null` and an existing empty adjacent line;
  standalone carriage returns follow JavaScript/Ohm column behavior.

Arbitrary `Interval.contents` boundaries that split an astral scalar return
exact WTF-8 lone-surrogate slices. Since intervals are copyable values, those
rare derived slices are interned by source identity and UTF-16 bounds; copies
therefore retain stable contents without double-free or dangling ownership.

Generated parsers expose:

```coil
(parse-tree input) ; -> experiments.ohm.runtime.MatchResult
(parse input)      ; -> bool
(parse-tree-from input rule-name) ; -> experiments.ohm.runtime.MatchResult
(parse-from input rule-name)      ; -> bool
(trace input)                     ; -> experiments.ohm.runtime.MatchResult
(trace-from input rule-name)      ; -> experiments.ohm.runtime.MatchResult
(to-ast input)                    ; -> experiments.ohm.runtime.OhmAst
(to-ast-from input rule-name)     ; -> experiments.ohm.runtime.OhmAst
(semantics-for-to-ast)            ; -> experiments.ohm.runtime.OhmToAstSemantics
(grammar)                         ; -> experiments.ohm.runtime.OhmGrammarDescriptor
(grammar-pexprs)                  ; -> experiments.ohm.runtime.OhmPExprGrammar
```

Grammar descriptors implement normalized structural equality. Their
source-independent fingerprints include grammar name, inherited lineage,
default start rule, sorted rule names, descriptions, formals, and normalized
expression strings. Consequently redundant grouping, whitespace, and rule
declaration order do not affect equality, while changed descriptions, default
starts, lineage, or rule sets do. The fingerprint can be inspected with
`--use experiments.ohm.grammar-fingerprint`.

`grammar-pexprs` exposes the public parsing-expression graph for every effective
rule, including inherited and overridden definitions. Nodes retain their Ohm
kind, nested children, decoded terminal/range/application text, UTF-16 source
interval, exact normalized `toString`, source-backed `toDisplayString`, and the
complete v17 `getArity()`, grammar-aware `isNullable()`, and
`toArgumentNameList(firstArgIndex)` algorithms. Nullability includes recursive
and parameterized applications; argument naming includes
alternation-column merging, duplicate subscripts, iteration pluralization,
optional prefixes, parameter names, identifier-safe ranges, and positional
terminal names. The implementation reads the byte-identical structural recipe
into a Coil JSON token tape at runtime; no JavaScript or Python implementation
path is involved. Recipe-reconstructed parsers expose the same graph.

`OhmAst` is an owned heterogeneous arena supporting null, string, boolean,
number, object, and array values, with ordered property and element traversal.
The Coil-native `toAST` mapping API supports rule templates, direct child
forwarding, renamed and static properties, explicit omission, boxed-number
equivalents, computed rule/property actions through a trait, lexical token
collapsing, transparent single-child syntactic rules, optionals, repetitions,
and the built-in lexical and syntactic list families. Its strings remain valid
after the source `MatchResult` and mapping are freed. Generated grammars expose
both convenience conversion functions and the `semanticsForToAST` counterpart;
the lower-level runtime entry point accepts an existing match and mapping.

`experiments.ohm.visitor-family` implements the grammar-independent
`VisitorFamily` extra over arbitrary Coil trees. Tree providers supply tags,
named scalar/array properties, and optional custom walker arguments through a
trait. Families support fixed and function-shaped nodes, lazy recursive
adapters, named operations with formal arguments, operation replacement,
dynamic action dictionaries, exact fixed-shape arity validation, and the
upstream unknown-action, unknown-tag, and missing-action diagnostics. Custom
shapes deliberately skip fixed arity validation, matching JavaScript function
shapes. `experiments.ohm.generic-visitor-family` supplies the fully typed ABI:
both operation arguments and recursive results are arbitrary Coil types. It
uses typed function-pointer callbacks because Coil's associated-result trait
forwarding remains broken; the runtime gate returns a real three-field struct
while accepting a distinct argument struct.

The remaining data-oriented extras are Coil-native as well.
`experiments.ohm.extract-examples` extracts signed JSON-string examples from
grammar comments, `experiments.ohm.recover-source-order` reverses Ohm's
column-transposed iteration bindings into source order, and
`experiments.ohm.stored-attributes` provides explicitly initialized semantic
attributes keyed by stable CST node identity. Stored attributes are read
through the normal semantic-action trait; skipped nodes fail with Ohm's exact
`Attribute '<name>' not initialized` diagnostic. The original handle ABI is
supplemented by `experiments.ohm.generic-stored-attributes`, whose cache stores
arbitrary typed Coil values and returns `Option<Value>` for the upstream
initialized/uninitialized distinction.

`experiments.ohm.recipe` is the Coil-native `makeRecipe` reader provider.
Source-backed JSON recipes decode escaped source, surrogate pairs, line and
paragraph separators, recursively order inline supergrammars, and compile the
result through the normal Ohm reader. Source-less recipes rebuild grammar
source from the recipe expression tree, including parameters, applications,
predicates, repetition, ranges, inheritance, rule operations, and Splice.
Recipe-generated grammars expose `to-recipe`; every recipe fixture checks an
exact byte-for-byte round trip. Grammars compiled directly from `.ohm` also
expose `to-recipe`; its valid JSON retains the exact source, effective grammar
name, and default start rule and can be fed back to
`--use experiments.ohm.recipe` to regenerate the parser. Its structural
grammar recipe is byte-identical to the pinned upstream serializer across all
120 conformance grammars for which upstream `toRecipe` succeeds.

The semantics runtime also has an executable, Coil-native recipe layer.
`semantics-to-recipe` snapshots the complete operation/attribute registry and
`make-semantics-from-recipe` reconstructs an independently owned registry,
preserving action order, formal counts, inherited/extended state, and the
actual action trait objects. The reconstructed extension is exercised against
a child-grammar match. Action objects and name slices retain their normal Coil
lifetimes. A separate persistent recipe format now stores the grammar recipe,
semantics name, ordered operation/attribute definitions, formal counts,
inheritance/extension flags, and deduplicated Coil action preambles plus
constructor expressions. `--use experiments.ohm.semantics-recipe` recompiles
the grammar and action source, reconstructs an independently executable
registry, and exposes `make-semantics`. Empty recipes round-trip byte-for-byte;
the action fixture executes a reconstructed operation against a reconstructed
grammar match. Actions must attach reconstructible source with
`set-semantics-action-recipe-source!`; an opaque trait object without source is
correctly reported as not persistently serializable rather than encoding its
process-local pointer.

`experiments.ohm.to-recipe` is the corresponding serializer entry point. It
compiles an ordinary Ohm grammar and writes its JSON recipe to stdout:

```sh
coil run grammar.ohm --use experiments.ohm.to-recipe > grammar.recipe.json
coil run grammar.recipe.json --use experiments.ohm.recipe
```

The emitted structure includes terminals, ranges, applications, parameters,
sequences, alternatives, predicates, repetition, inline-case rules, inherited
splice placement, exact rule/expression source intervals, default-start
semantics, and recursively inlined user supergrammar recipes. The structural
fixtures are compared byte-for-byte with the pinned Ohm serializer.

Trace results retain a parent-linked preorder arena independently from the CST,
so failed alternatives remain inspectable after CST rollback. The runtime
exposes event count, parent/child traversal, display string, input interval,
grammar-expression source interval, success, ordered CST-binding arrays,
synthetic-root bindings, implicit-space, memoization, and left-recursion accessors.
It also provides Ohm-style string rendering and a Coil visitor with enter,
exit, and skip semantics. Every positive fixture constructs and structurally
validates a generated matcher trace. Translated upstream fixtures assert exact
basic, memo-replay, parameterized-memo, and left-recursion rendering, plus
syntactic-space, parameterized-rule, case-insensitive, and inherited `...`
splice topology. All 13 top-level cases in `test-tracing.js` are translated,
including the two cases marked `test.failing` upstream: duplicate memoized LR
applications retain their distinct grammar-source intervals, and expression
traces expose complete ordered binding arrays plus the synthetic top-level
`end` binding.

The `*-from` entry points dispatch to declared rules and built-ins, including
inherited built-ins in an otherwise empty user grammar. Parameterized start
applications accept arbitrary well-formed, arity-one parsing expressions,
including nested parameterized user-rule applications, applications that were
not otherwise specialized by the grammar, and parameterized left recursion.

`experiments.ohm.runtime.OhmLazySemanticAction` is the Coil-native lazy
semantics surface. Operations receive scoped arguments and explicitly invoke
children; attributes memoize per node and support subtree invalidation and
cycle detection. Dispatch distinguishes exact ctor actions, `_nonterminal`,
and user `_default` actions, then applies Ohm's built-in one-child forwarding
default. Semantic action layers can delegate to inherited layers, and match
results retain their complete grammar lineage for inherited parser metadata.
Semantic application requires both the declared grammar name and an opaque
per-grammar static token: parent semantics are rejected on a child grammar's
match, unrelated grammar objects that reuse a name remain distinct, and an
extended child semantic layer can delegate to its inherited actions. Generated match results also carry
constructor arities for user rules, inherited overrides, inline cases, and
built-ins. Action schemas reject unknown and duplicate keys, wrong action
arities, malformed special actions, and attributes with formal arguments.
Failed lazy evaluation retains its ordered semantic action stack for
diagnostics. `_iter` actions evaluate mapped children, distinguish optional
nodes, and correctly fail when no iteration action is supplied. Wrapper
predicates expose terminal, iteration, nonterminal, syntactic, and lexical node
kinds. `experiments.ohm.generic-semantics` additionally provides a typed
callback action table whose result is an arbitrary Coil type. Its executable
coverage returns a user-defined struct through lazy, recursive child
evaluation. This avoids restricting semantic values to scalar handles while
the documented Coil associated-result and trait-bound-forwarding compiler
paths remain unavailable.

`MatchResult` owns a flat CST arena. Each rule node contains a stable identity,
its rule name,
source start/end, first/last child, and next-sibling index. Backtracking uses
transactional arena marks, so nodes produced by failed alternatives, optional
matches, repetition probes, and predicates do not leak into successful trees.

Every positive conformance case checks:

- successful full-input recognition;
- a valid root index;
- the expected root rule name;
- the exact root source span;
- structural validity of every child/sibling chain and nested source span.

All 339 recognition directives in the positive corpus are also evaluated by
the pinned Ohm.js build during differential auditing. Their construction and
accept/reject outcomes currently have zero mismatches. Coil-only assertions
then add CST shape, failure metadata, trace, incremental-cache, semantics, and
recipe checks that cannot be expressed by recognition alone.

Every successful directive is additionally compared as a complete CST against
the pinned build. The signature includes every constructor name, ordered child,
iteration wrapper, node source string, and absolute UTF-16 source interval. All 243 successful directive trees
across the 145 positive fixtures currently match exactly. This differential is
run through `--use experiments.ohm.cst`; the provider changes only the generated
fixture entry point, while parsing and CST construction use the production Coil
runtime.

The Coil-native fixtures are in `tests/ohm/conformance`. They use comments so
they remain valid Ohm grammar files:

```ohm
// @accept accepted input
// @reject rejected input
// @accept-node required_case_rule accepted input
// @accept-iter columns rows optional accepted input
```

`@accept-iter` asserts the exact Ohm 17 column-transposed binding shape at the
root, including the optional flag; it is not merely a recognition check.

Run the current suite with:

```sh
for fixture in tests/ohm/conformance/*.ohm; do
  coil run "$fixture" --use experiments.ohm.lang || exit 1
done
coil run tests/ohm/ohm-grammar.ohm --use experiments.ohm.lang
```

For a newline-delimited, unambiguous CST signature of every successful fixture
directive, replace the provider with `experiments.ohm.cst`.

Negative grammar-construction and matcher-lifecycle fixtures are in
`tests/ohm/errors`; each is expected to fail through the same
`--use experiments.ohm.lang` path with the corresponding Ohm-style diagnostic.
The 43 construction fixtures that have direct equivalents exercised by the
pinned JavaScript API, two namespace failures, and five dynamic matcher
failures are also compared against upstream in full: line and
column, surrounding source lines, UTF-16-aligned caret/range, validation order,
and final diagnostic text. This differential caught and now covers lexical
validation before parameter specialization, base-grammar validation before a
descendant is merged, immediate-supergrammar attribution for duplicate rules,
and the distinction between an absent default start rule and an undeclared
named rule.

## Namespace and input model

`experiments.ohm.grammar` is the strict `ohm.grammar()` analogue. It accepts
exactly one definition and reports Ohm's source-ranged “Found more than one
grammar definition -- use ohm.grammars() instead.” error for a second.
`experiments.ohm.lang` retains the convenient final-grammar interface for a
same-file inheritance chain, while `experiments.ohm.namespace` is the
multi-grammar `ohm.grammars()` analogue.

`experiments.ohm.namespace` supports same-source namespaces and recursive
compile-time namespace imports with `// @namespace-import path`. Imported
grammars are visible to local declarations and supergrammar lookup; duplicate
declarations are rejected across the full imported namespace. Independent
child compilations may declare distinct grammars with the same public name
while sharing an imported parent definition. Namespace dispatch returns either
booleans or complete `MatchResult` trees.

Coil parser inputs are typed `(slice u8)` byte strings. Ordinary text uses
UTF-8; WTF-8 encodings preserve JavaScript lone-surrogate code units, including
the `Cs` Unicode category. JavaScript's arbitrary-object and `toString`
coercions are intentionally represented by this typed boundary rather than by
runtime host-object reflection.

## Upstream suite mapping

At the pinned revision, the checked-in inventory tool finds 24 executable test
files containing 220 statically declared tests and 912 recognizable AVA
assertion call sites, including the executable documentation suite, CommonJS
examples, and the example pretty-printer tests. Generated/looped assertions
make the assertion count a lower bound. The ten top-level tests in `test-recipes.js` are
tracked separately: all grammar-recipe cases (empty/simple, inheritance,
parameterized rules, retained or absent source, U+2028/U+2029 escaping, and
astral code points) are covered. Executable in-memory semantics reconstruction
and extensions are covered. Persistent semantics recipes compile and execute
empty registries, scalar operations, operations with formal arguments,
operation-to-attribute calls, inherited/extended registries, unusual Unicode
rule/action names, and separator-safe embedded source.

Top-level file audit ("covered" means every top-level case has a translated
behavioral counterpart; "partial" means the listed public surface is still
missing):

| Upstream file | Cases | Status | Remaining surface |
| --- | ---: | --- | --- |
| `_test-doc.js` | 4 | covered by Coil API examples | — |
| `examples/test-prettyPrint.js` | 3 | covered | — |
| `test-built-in-rules.js` | 5 | covered | — |
| `test-errors.js` | 15 | covered | — |
| `test-examples.cjs` | 3 | covered by Coil analogue | Exact math/viz and CSV recognition plus 19/19 complete CSTs; arithmetic `interpret`, memoized structural `asLisp`, and both exact CSV `value` results execute through generated parsers |
| `test-findIndentation.js` | 1 | covered | — |
| `test-grammar.js` | 3 | covered | — |
| `test-incremental.js` | 14 | covered | — |
| `test-indentation-sensitive.js` | 7 | covered, including upstream's skipped #467 | — |
| `test-input-stream.js` | 1 | covered | — |
| `test-interval.js` | 10 | covered | — |
| `test-main.js` | 3 | covered by Coil analogue | typed byte inputs and compile-time namespace imports replace JavaScript host-object coercion |
| `test-ohm-syntax.js` | nested | covered | — |
| `test-parameterized-rules.js` | 10 | covered | — |
| `test-pexprs.js` | 5 | covered | — |
| `test-recipes.js` | 10 | covered by Coil analogue | JavaScript method-shorthand identity is represented as Coil action source |
| `test-semantics.js` | 17 | covered | — |
| `test-tracing.js` | 13 | covered | — |
| `test-util.js` | 3 | covered | — |
| `extras/test-extractExamples.js` | 8 | covered | — |
| `extras/test-recoverSourceOrder.js` | 1 | covered | — |
| `extras/test-storedAttributes.js` | 1 | covered | — |
| `extras/test-toAST.js` | 6 | covered | — |
| `extras/test-visitorFamily.js` | 6 | covered | — |

This audit intentionally prevents the passing translated gate from being
mistaken for 100% public-API compatibility. The partial rows are the current
completion queue.

The PExpr row has a complete recursive public-value oracle, not only focused
assertions. Run:

```sh
node tests/ohm/upstream-pexpr-differential.mjs /path/to/pinned/ohm
```

For each of the five upstream grammars it compares every effective user rule's
name, definition interval, description, formals, and entire expression graph.
Every node includes kind, public fields, source interval, `toString`,
`toDisplayString`, arity, nullability, argument names, and ordered children.
An additional projection compiles the inheritance fixture through the
`ohm.grammars()` namespace analogue and verifies that inherited and local
intervals share the complete namespace source with absolute offsets. The gate
is currently 6/6 exact. It specifically guards `Extend` retaining both
the new and inherited bodies; recognition-only coverage previously hid the
loss of that public structure.

The Grammar-object oracle runs with:

```sh
node tests/ohm/upstream-grammar-differential.mjs /path/to/pinned/ohm
```

It compares both complete upstream operation/attribute action-dictionary
template snapshots and seven default-start configurations: empty, first own
definition, extension-only, extension followed by a definition, override-only,
override followed by a definition, and inline-case exclusion. The gate is 9/9
exact. Structural equality mutation and recursive-supergrammar behavior remain
covered by `grammar-equality-runtime.coil`; that runtime also calls the distinct
operation- and attribute-template API names.

The Interval and `LineAndColumnInfo` public-value oracle runs with:

```sh
node tests/ohm/upstream-interval-differential.mjs /path/to/pinned/ohm
```

It is currently 13/13 exact across collapse, coverage, trimming, subintervals,
UTF-16 positions, CRLF, standalone carriage returns, and absent versus empty
previous/next lines. Source-mismatch and relative-coverage error paths remain
covered by the exact diagnostics gate.

The public incremental Matcher lifecycle oracle runs with:

```sh
node tests/ohm/upstream-matcher-public-differential.mjs /path/to/pinned/ohm
```

It is 7/7 exact across chained edits, `setInput`, default and explicit start
rules, success/failure positions and expected text, left recursion, lookahead,
and complete CSTs after each mutation.

The `extractExamples` extra has an exact data projection:

```sh
node tests/ohm/upstream-extract-examples-differential.mjs /path/to/pinned/ohm
```

It is 16/16 exact across all upstream case shapes plus comma-separated JSON
strings, BMP escapes, surrogate pairs, and multiple grammars. This gate found
and now guards the escape-cursor bug that formerly leaked the final four hex
digits after a decoded `\uXXXX` escape.

The complete `toAST` and `semanticsForToAST` public-value projection runs with:

```sh
node tests/ohm/upstream-to-ast-differential.mjs /path/to/pinned/ohm
```

It is 22/22 exact. Recursive signatures cover defaults, renamed/static/omitted
and boxed properties, computed property and rule actions, forwarded children,
explicitly reintroduced nodes, optionals, repetitions, lexical and syntactic
list families, overridden list mappings, and the `semanticsForToAST` operation
surface and application. Builder-generated final grammars expose the latter as
a directly callable `semantics-for-to-ast` entry point.

The VisitorFamily projection runs with:

```sh
node tests/ohm/upstream-visitor-family-differential.mjs /path/to/pinned/ohm
```

It is 8/8 exact across fixed and array properties, recursive adaptation,
operation arguments, all upstream arity/action-name diagnostics, prototype
property tag rejection, and the typed arbitrary-struct analogue. The original
`i64` ABI remains useful for handles, while the generic ABI removes that former
result/argument restriction.

The remaining data extras have exact projections:

```sh
node tests/ohm/upstream-recover-source-order-differential.mjs /path/to/pinned/ohm
node tests/ohm/upstream-stored-attributes-differential.mjs /path/to/pinned/ohm
```

They report 5/5 and 6/6 exact comparisons. The source-order gate covers every
upstream nested, optional, and column-transposed case with exact constructor
names and UTF-16 intervals. The stored-attribute gate compares all five
initialized polarity paths plus the skipped operator's uninitialized state,
while its Coil side stores a real `{text, rank}` struct rather than encoding
the value as an integer. `stored-attributes-runtime.coil` separately guards the
exact `Attribute 'polarity' not initialized` message.

### `test-semantics.js` case ledger

The 17 upstream cases map to focused executable evidence as follows. This is a
case-level map; individual assertions remain identifiable by the stable IDs
emitted by `upstream-assertion-inventory.mjs`.

| Upstream case | Coil evidence |
| --- | --- |
| operations; operations with arguments | `semantic-action-runtime.coil` lazy operation values, formal counts, nested operation dispatch, and exact argument-count failure |
| attributes; same-named attributes | independent attribute caches, memo hits, explicit forgetting, and incremental transfer in `semantic-action-runtime.coil` |
| semantics | registry duplicate/kind/signature validation, failed-match and grammar-identity rejection |
| `_iter` nodes; `_terminal` nodes | iteration mapping/optional metadata and exact missing-action diagnostics |
| semantic action arity checks | `OhmSemanticActionSchema` validates rule, special-action, rest, duplicate, and inherited arities |
| extending semantics | inherited/extended operation and attribute registries plus reconstructed semantics recipes |
| mixing grammar nodes | opaque grammar-token rejection, including unrelated grammars with the same name |
| `asIteration` | built-in lists, empty lists, synthetic child slices, reversal, and lazy child evaluation |
| `sourceString`; issues #188 and #204 | exact nonterminal/iteration source spans plus generated CSV list semantics |
| action call stacks | both upstream exact multiline stack messages, including a cross-operation call |
| incorrect `_iter`/`_nonterminal` arity | special rest-arity schema failures and exact iteration missing-action guidance |
| inner NodeWrapper `toString` (#416) | `semantics-to-string-runtime.coil` invokes wrapper rendering inside an inner `letter` action and compares the exact text |

The ordinary lazy ABI returns `i64`, which is also usable as an owned value
handle. `experiments.ohm.generic-semantics` separately proves arbitrary typed
struct results over both a manually constructed CST and an actual
Builder-generated parser. Merging those surfaces behind a single generic action trait is
not yet claimed: `generic-result-trait-repro.coil` records the remaining Coil
associated-result unification failure without introducing primitive collection
access into the production implementation.

All 14 top-level tests in `test-incremental.js` are translated. Coverage
includes exact per-rule match length, examined length, and rightmost-failure
offset records for non-left-recursive and left-recursive grammars; the complete
public edit workflow; constructor-tree changes after lookahead invalidation;
lexical and syntactic binding offsets; and the arithmetic attribute test's
exact recomputation sequence (`8`, then `2`, then `5` freshly evaluated
attributes).

All 13 top-level tests in `test-tracing.js` are translated, including the two
cases that upstream itself marks as expected failures for its incremental
parser. Coil validates expression source intervals, memoized left-recursion
metadata and bindings, multi-binding alternatives, and the synthetic trace
root's start-plus-end binding sequence. The complete serialized trace trees
for all 13 cases—including display strings, UTF-16 intervals, flags, CST
bindings, sparse `undefined` children, memo replay, and terminating
left-recursion entries—are byte-for-byte identical to pinned Ohm 17.2.1.

Implementation order:

1. `test-ohm-syntax.js`, `test-pexprs.js`, and `test-built-in-rules.js` matcher
   behavior and CST shape.
2. `test-parameterized-rules.js`, grammar inheritance, and left-recursion
   sections from `test-ohm-syntax.js`.
3. `test-errors.js`, intervals, and failure-position tests.
4. `test-semantics.js` plus semantics extension tests.
5. Incremental matching, tracing, indentation-sensitive matching, recipes,
   and extras.

The current repository gate contains 145 positive grammar fixtures, 19 recipe
fixtures, and 53 negative grammar-construction, PExpr, or matcher-lifecycle fixtures,
in addition to 23 external Coil runtime consumers and canonical
`ohm-grammar.ohm` bootstrap checks. These counts
describe the translated coverage currently present; they are not a claim that
the full upstream JavaScript test suite passes yet.

The semantics runtime also constructs synthetic iteration wrappers without
mutating the CST. Coverage includes existing `_iter` nodes, empty `ListOf`,
nonempty `ListOf` column flattening, arbitrary child slices, reversal, and lazy
evaluation of the resulting children. Applying semantics to a failed match is
rejected when the semantic evaluation is created, matching Ohm's lifecycle
rule rather than deferring the failure until node dispatch.

Named semantic evaluations produce Ohm-compatible argument-count and missing
action diagnostics. Missing actions include the retained action stack, explicit
versus default-action labels, terminal/iteration constructor names, and the Ohm
v16 `_iter` migration note. The canonical `start -> digit -> _terminal` message
from upstream `test-semantics.js` is checked byte-for-byte. Frames retain their
own operation names, and the upstream mixed-operation `op2 -> oops` stack is
also checked byte-for-byte.

Source interval coverage includes nonterminals, terminals, and iteration nodes,
including the upstream issue #188 case where a parent's source contains skipped
spaces but each child's `sourceString` does not. Separate same-named attribute
evaluations maintain independent memo tables.

`OhmSemantics` is the Coil-native named action registry. It adds operations and
attributes, rejects duplicate names, grammar mismatches, and attribute formal
arguments, clones inherited definitions for a child grammar, enforces one-time
extension and operation/attribute kind agreement, and creates named lazy
evaluations from registered actions. Introspection enumerates operation and
attribute names, formal counts, and inherited/extended state. Generated
grammars expose `action-dictionary-template`; both the base G1 and inherited G2
snapshots from upstream `test-grammar.js` are checked byte-for-byte. The
built-in `end` CST and template entry both have Ohm's one-child semantic arity.
Operation signatures accept Unicode names, whitespace, empty or comma-separated
formal lists, and validate their count against the typed action. Attribute and
extension signatures reject formal lists, matching Ohm's construction rules.
Semantics registries and wrappers, including inner CST nodes, expose Ohm's exact
`[semantics for G]` and `[semantics wrapper for G]` string forms.

Generated grammars expose `matcher()`. `OhmMatcher` owns mutable input, supports
validated range replacement and alternate start rules, and returns matches with
owned source snapshots so earlier `MatchResult`s and their diagnostics remain
valid after later edits. It exposes incremental match and trace entry points.
Every positive fixture executes repeated generated matcher calls;
`matcher-runtime.coil` covers successive failure/failure/success edits. Memo
records and their CST, failure, and trace snapshots persist between matches.
Snapshot storage is append-only per capture: recapturing an outer memo entry
updates that entry's segment pointers without truncating or overwriting segments
owned by nested entries. The multiline CSV differential specifically guards
against the former corruption where replaying `eol` could return a nested
`col` or `_iter` node. Edits compact and shift unaffected suffix and prefix records according to each
rule's exact examined range. Memo records retain failures suppressed by
backtracking and count end-of-input probes one position beyond the source, as
Ohm does. Stable CST identities survive both direct memo replay and replay of a
cached parent whose descendant memo records were elided. Incremental attribute
evaluations transfer a semantics-specific cache across results and reproduce
the pinned arithmetic suite's exact selective recomputation behavior.
Every named semantics registry also owns an independent cache for each
attribute. Registered evaluation construction and teardown transfer that cache
automatically; inherited and recipe-reconstructed semantics allocate fresh
caches, process-unique CST identities prevent unrelated matches from
colliding, and stable identities still reuse unchanged incremental subtrees.
The separate public Matcher differential compares seven complete observable
states byte-for-byte with pinned Ohm, including full CSTs after mutation.

Match failure messages include Ohm's aligned previous/current/next-line context,
the caret gutter, and the independent one-line `shortMessage`. Rightmost failure
positions, expectation subsumption/fluffiness, descriptions, memo replay, and
ordered failure inspection are also covered.

Tests are translated into Coil fixtures rather than shipping or invoking the
JavaScript implementation. Ohm.js may be used during development as a
differential oracle, but generated parsers and the conformance implementation
remain Coil-only.
