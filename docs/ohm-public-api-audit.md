# Ohm 17.2.1 public API audit

Authoritative surface: `packages/ohm-js/index.d.ts`, `index.mjs`, and
`extras/index.d.ts` at upstream revision
`43c345b920c98b3eb13ce6b12df2b6ebd400b63b`.

This is a live completion ledger. A translated top-level test is not sufficient
evidence for an API marked complete; each row requires a callable Coil surface
and a focused behavioral gate.

| Surface | Coil representation | Status / evidence |
| --- | --- | --- |
| `grammar`, `grammars` | `experiments.ohm.grammar`, `.namespace`, and `.lang` reader providers | Implemented for the metaprogram `--use` model; namespace and strict-single-grammar gates pass |
| `makeRecipe` | `experiments.ohm.recipe` reader provider | Implemented; 19 grammar/semantics recipe gates pass |
| `ohmGrammar` | canonical `ohm-grammar.ohm` compiled by the reader | Self-parse gate passes |
| `ExperimentalIndentationSensitive` | generated `experimental-indentation-sensitive-grammar-object` plus inherited `IndentationSensitive` support | Implemented as an executable non-incremental grammar value with exact `indent`, `dedent`, and extended `any` own-rule graphs; generated descendant grammars expose the correct `IndentationSensitive → BuiltInRules → ProtoBuiltInRules` ancestry, including upstream #467 behavior |
| `version` | `experiments.ohm.runtime.OHM-VERSION` | Implemented (`17.2.1`) |
| `_buildGrammar` / programmatic `Builder` and `GrammarDecl` | `experiments.ohm.builder-lang`, recipe compiler, and direct PExpr constructors | Implemented as a Coil read-phase metaprogram: grammar chains, explicit supergrammars/default starts, rule descriptions/formals, `define`/`override`/`extend`, ordered `Splice`, and all public v17 expression constructors compile to executable specialized Coil through `--use` |
| `Grammar` matching, tracing, matcher, semantics, equality, recipe, action templates | generated `OhmGrammar` (`grammar-object`) plus descriptor compatibility API | The cohesive owned value contains executable parser entry points and the complete PExpr rules graph; it creates matchers and semantics, directly matches/traces with retained matcher ownership, and exposes identity/source/recipe/template metadata. Equality recursively compares the current grammar and structural supergrammar chain, including names, defaults, and sorted own-rule descriptions/formals/bodies, so public mutation is observable just as in Ohm. Distinct operation- and attribute-template entry points mirror the two upstream method names while returning their shared exact template. A pinned differential is 9/9 exact across both upstream template snapshots and seven default-start configurations. `isBuiltIn` uses explicit canonical identity rather than the grammar name: a user-created grammar named `BuiltInRules` remains non-built-in. User-grammar `superGrammar` is navigable in namespace-generated chains. Ordinary roots expose `BuiltInRules`, whose supergrammar is `ProtoBuiltInRules`; their rule graphs and action-dictionary templates match pinned Ohm exactly. `ProtoBuiltInRules` and `IndentationSensitive` preserve the exact abstract `toRecipe` failures. The canonical built-in grammar is compiled as an independent hidden specialization, so matching through an ancestor cannot observe descendant overrides of scalar, list, or parameterized built-ins. |
| `pexprs` expression graph | `OhmPExprGrammar` / `OhmPExprNode` | Exact source/string/display/argument names, `withSource`, v17 arity and recursive/parameterized nullability, Builder-compatible flattened alternatives/sequences, and direct constructors including `CaseInsensitiveTerminal`, extension, splice, `any`, and `end` implemented. A recursive public-graph differential covers all 36 assertions in upstream `test-pexprs.js`; five single/separately-constructed grammar projections plus the `ohm.grammars()` namespace projection are 6/6 byte-exact. |
| `Matcher` | `OhmMatcher` | Retained public grammar association, chainable UTF-16-indexed input replacement (including edits between surrogate halves through WTF-8), set/get, match/trace, start applications, incremental cache and invalidation implemented; standalone generated matchers own their grammar and release it safely. A seven-state public lifecycle differential compares exact inputs, success/failure metadata, alternate starts, and complete CSTs after edits. |
| `MatchResult` | `MatchResult` | success/failure, messages, ordered rightmost failures with exact `string`/`description`/`code` type names and fluffy predicates, expected text, UTF-16 rightmost position, interval, exact `toString`, and retained public matcher association implemented |
| semantic `Node` | CST arena node index plus `MatchResult` | ctor/source/sourceString/children/kind/optional/asIteration and child navigation implemented |
| `Interval` | `OhmInterval` | collapse, coverage, source identity, difference, relative, trim, subinterval, line/column, exact half-surrogate contents, and exact source-mismatch/relative-coverage failures implemented and gated; a 13-case pinned public-value differential is exact |
| `InputStream` | `OhmInputStream` | UTF-16 position/examined-length behavior, code-unit/code-point reads, matching, intervals, JavaScript-style source slicing, and exact lone-surrogate slices implemented and gated |
| `LineAndColumnInfo` / util exports | `LineColumn` plus rendering helpers | UTF-16 offset, line/column, current line, optional previous/next lines (preserving `null` versus an empty line), standalone-CR behavior, and exact ranged rendering implemented |
| `Semantics` | `OhmSemantics`, lazy action traits, typed generic semantics | operations, attributes, extension, structural same-source and supergrammar compatibility validation, exact unrelated-grammar rejection, memoization, recipes, wrapper kinds and `asIteration` implemented |
| `Trace` | trace arena attached to `MatchResult` | Complete 13-case upstream serialized differential is exact; walking and string rendering implemented |
| extras: `toAST`, `semanticsForToAST`, `VisitorFamily`, `extractExamples`, `recoverSourceOrder`, stored attributes | dedicated Coil modules/providers | Implemented with focused runtime gates. `toAST`/`semanticsForToAST` have a 22/22 exact recursive-value projection covering the complete upstream mapping and list behavior; Builder output now exposes a directly callable final-grammar `semantics-for-to-ast`. `VisitorFamily` has an 8/8 pinned behavioral projection and a typed callback ABI whose operation arguments and results can be arbitrary Coil structs rather than the original narrowed `i64` representation. `extractExamples` is 16/16 exact. `recoverSourceOrder` is 5/5 exact across the complete upstream nested/optional corpus. Stored attributes are 6/6 exact and now have a generic stable-node cache for arbitrary struct values, while retaining the exact uninitialized-attribute diagnostic. |

The reproducible inventory command
`node tests/ohm/upstream-assertion-inventory.mjs <pinned>/packages/ohm-js/test`
currently finds 220 statically declared tests and 912 recognizable AVA
assertion call sites across 24 executable files (plus the assertion-free helper
module). Generated/looped assertions make 912 a lower bound. The existing
translated corpus is valuable evidence, but completion additionally requires a
case-by-case mapping of this denominator rather than relying only on file-level
labels.

Current stable regression evidence: 145/145 positive grammar fixtures, all 53 negative grammar fixtures rejecting as intended, 31/31 runtime
programs using their documented providers, 7/7 namespace programs, 19/19 recipe programs, canonical
`ohm-grammar.ohm` self-parsing, and 13/13 serialized trace trees (49,525 bytes)
exactly matching pinned Ohm 17.2.1. These gates prove the listed behavior; they
do not by themselves prove the remaining incomplete public surfaces.

The corpus-wide public-CST oracle runs every successful directive in all 145
positive fixtures through both pinned Ohm and Coil. It currently reports
243/243 exact recursive trees with no skipped grammars. This gate compares
constructor names, child order, source strings, and absolute UTF-16 intervals;
it also guards the public-root interval behavior of arity-changing dynamic
start applications, which differs from Ohm's private `_cst` match length.

The upstream browser-example consumer audit additionally compares 19 complete
CSTs from the exact math/viz arithmetic and CSV grammars, including both
multiline CSV inputs, empty rows and columns, a trailing newline, all ten viz
inline cases, and the standalone `eol` rule. All 19 currently match exactly.
Two additional Builder-provider runtime consumers execute the example-level
semantics: arithmetic `interpret` and memoized structural `asLisp`, plus CSV
`value` over the exact six-row result with and without its final newline.

Construction-time diagnostics have an additional byte-exact oracle. Running
`node tests/ohm/upstream-error-differential.mjs <pinned-ohm-repository>`
currently compares all 43 fixtures for which public `ohm.grammar()` rejects,
plus the directly comparable duplicate/undeclared `ohm.grammars()` cases and
five dynamic matcher failures (nullable expressions, parameterized defaults,
missing defaults, and incorrect dynamic parameter counts), plus the exact CST
for an arity-changing dynamic argument, and reports 51/51 exact comparisons
after removing only Coil's command-line `error: `
prefix. The experimental-indentation incremental fixture is excluded
because its upstream construction requires the non-public experimental
namespace; its intended runtime rejection has a separate focused gate.
