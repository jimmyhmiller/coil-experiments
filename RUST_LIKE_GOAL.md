# Goal: Complete CoilRS Rust-Like Reader With Zero Native Fallbacks

Implement and ship a production-quality reader metaprogram that allows Coil
programs to be written in Rust-like syntax while preserving the complete
expressive power and exact syntax-tree structure of native Coil.

The implementation is not complete until every requirement and verification
gate below passes.

## Non-negotiable constraints

1. All production functionality must be implemented in Coil.
2. Python must not implement, generate, parse, translate, convert, execute, or
   support any part of the Rust-like reader or conversion pipeline.
3. The production implementation must not invoke Python indirectly through
   subprocesses, shell commands, generated scripts, or temporary files.
4. The language and package must be named `rust-like`, including:
   - Directory: `src/dialects/rust-like/`
   - Reader namespace: `experiments.rust-like.reader`
   - Language namespace: `experiments.rust-like.lang`
   - Converter namespace: `experiments.rust-like.convert`
5. Converted programs must never contain verbatim native Coil fallbacks,
   including:
   - `coil { ... }`
   - `coil_item { ... }`
   - `coil_expr { ... }`
   - Native Coil source hidden inside strings
   - Any differently named construct serving the same purpose
6. Converted output must never contain generic syntax-tree constructors such as
   `form!(...)`, `atom!(...)`, `item form!(...)`, or renamed equivalents. These
   are AST serialization, not Rust-like source syntax.
7. Backtick-escaped identifiers may be emitted only when a name cannot be
   represented by ordinary Rust-like identifier or path syntax. They must not
   be used as the default spelling for names.
8. No construct may be silently dropped, approximated, reordered, renamed, or
   semantically altered merely to make conversion succeed.

## Required language behavior

The reader must support every construct documented in
`src/dialects/rust-like/README.md`, including:

- Modules
- Imports, aliases, exclusions, renames, and reexports
- Exports
- Constants
- Functions
- Parameters and return types
- Generic parameters and bounds
- Parameter packs
- Type applications
- Structs
- Sum types/enums
- Traits
- Trait implementations
- Inherent implementations
- Derives
- Annotations
- Foreign declarations
- C imports and exports
- Immutable and mutable bindings
- Places, loads, stores, and assignments
- Compound assignments
- Function calls
- Generic calls
- Struct and variant construction
- Fields and indexing
- Array/vector literals
- Unary and binary operators with correct precedence
- `if`
- `when`
- `unless`
- `match`
- `cond`
- `case`
- `loop`
- `while`
- `for`
- `break`
- `continue`
- Named blocks and `return_from`
- Compile-time expressions
- Metaprogram blocks
- Checkers
- Transforms
- Quote, quasiquote, unquote, and splice
- A readable Rust-like macro-call syntax for arbitrary user-defined and future
  Coil forms

Every documented example must be executable syntax, not aspirational
documentation.

## Conversion requirements

The Coil-to-CoilRS converter must:

1. Be implemented entirely in Coil.
2. Accept every valid native Coil syntax tree.
3. Produce valid Rust-like source.
4. Prefer dedicated readable syntax for every supported documented construct.
5. Use readable Rust-like macro-call syntax for genuinely open-ended forms;
   never expose parser AST constructors.
6. Never emit a native-source escape.
7. Produce deterministic output.
8. Preserve exact form ordering and syntax-tree structure.
9. Preserve symbols, keywords, strings, C strings, characters, integers, floats,
   vectors, lists, and quote forms exactly at the syntax-tree level.

The tree converter must convert an entire Coil checkout without excluding valid
production `.coil` files merely because they are difficult to parse.

Files that intentionally contain malformed source as test data may be copied as
data, but this exception must be explicit and narrowly identified. It must not
become a general directory exclusion that hides valid programs.

## Exact round-trip requirement

For every valid native Coil input `P`:

```text
native Coil P
    -> Coil-native converter
    -> Rust-like source R
    -> Coil-native Rust-like reader
    -> native Coil syntax tree P′
```

`P′` must be structurally identical to `P`.

Comparison must cover the complete parsed `Code` tree after removing source-span
metadata only. Pretty-printed text equivalence is insufficient.

The following differences are failures:

- Changed atom values
- Changed atom kinds
- Changed list/vector kinds
- Changed nesting
- Changed quoting
- Changed ordering
- Added or removed forms
- Numeric corruption
- Symbol normalization
- String or character corruption

## Bidirectional usability requirement

A programmer must be able to:

- Write a program directly in pleasant Rust-like syntax.
- Convert native Coil to Rust-like syntax.
- Edit the converted Rust-like program.
- Compile that Rust-like program directly.
- Convert it back to a structurally identical native Coil program.
- Mix dedicated constructs and readable open-ended macro calls in the same file.

This must work through the normal Coil reader-provider mechanism, not through a
separate wrapper pretending to be a reader.

## Required fixtures

All Rust-like fixtures must compile and run successfully:

```sh
coil run tests/rust/structured.coilrs --use experiments.rust-like.lang
coil run tests/rust/surface.coilrs --use experiments.rust-like.lang
coil run tests/rust/advanced.coilrs --use experiments.rust-like.lang
coil run tests/rust/ffi.coilrs --use experiments.rust-like.lang
coil run tests/rust/embedded.coil
```

The test corpus must include at least one executable or syntax-tree assertion
for every documented construct.

Having one simple fixture pass does not establish language completeness. The
entire converted compiler must also contain zero occurrences of `form!(`,
`atom!(`, or `item form!`, and must not default to backtick-escaping ordinary
identifiers.

## Repository-wide verification

The final test harness must:

1. Reject Python references in the production Rust-like implementation.
2. Check every Coil module belonging to the reader and converter.
3. Run every Rust-like surface fixture.
4. Test exact syntax-tree round trips for representative edge cases.
5. Convert every valid production Coil source in the repository.
6. Verify every converted source can be read again.
7. Verify no converted file contains native fallback syntax.
8. Compare every original and restored syntax tree.
9. Fail if any file is skipped without an explicitly documented data-file
   exception.
10. Exercise strings, comments, delimiter characters, character literals,
    numeric extremes, quotes, vectors, macros, and unusual symbols.

## Full compiler gate

A clean copy of the complete Coil compiler must be converted to Rust-like
syntax.

The converted checkout must then build its compiler from the converted
`.coilrs` entry point:

```sh
coil build src/compiler/main_a64.coilrs \
    --use experiments.rust-like.lang \
    -o /tmp/coil-rust-like
```

The resulting compiler must execute successfully:

```sh
/tmp/coil-rust-like --version
```

This gate is a failure if:

- A production compiler source was left in native Coil solely to avoid
  conversion.
- A native fallback was emitted.
- Python participated in conversion or reading.
- The build used the original native entry point.
- The resulting executable cannot run.
- The converted compiler does not use the converted source tree as its standard
  library/checkout.

## Documentation requirement

`src/dialects/rust-like/README.md` must accurately describe the implemented
language.

It must not:

- Document syntax that the reader rejects.
- Describe removed Python commands.
- Claim native fallbacks exist.
- Claim completion based only on structural conversion.
- Use obsolete `rust.lang` or `experiments.coilrs` names.

Every syntax example in the document must be included in automated conformance
testing.

## Cleanliness requirement

Before completion:

- Delete every Python file introduced for this implementation.
- Delete obsolete `src/dialects/rust/` files.
- Remove stale commands and fallback terminology.
- Ensure `AGENTS.md` records the prohibition on Python production functionality.
- Preserve unrelated user changes.
- Confirm `git status` contains only intended changes.

## Delivery requirement

After every preceding gate passes:

1. Review the complete diff.
2. Run the complete test suite.
3. Run the full compiler conversion/build/execution gate.
4. Search for Python integration and native fallback mechanisms.
5. Commit all pending intended changes.
6. Push the commit successfully.
7. Report the commit hash and pushed branch.

## Definition of done

The goal is complete only when all of the following are simultaneously proven:

- The reader and converters are implemented in Coil.
- Every documented Rust-like construct works.
- Every valid Coil syntax tree has a non-native-fallback Rust-like
  representation.
- Exact native → Rust-like → native syntax-tree round trips pass
  repository-wide.
- All Rust-like fixtures compile and run.
- The fully converted Coil compiler builds and runs.
- No production Python implementation remains.
- No native fallback mechanism remains.
- Documentation matches reality.
- All intended pending changes are committed and pushed.

Partial syntax support, structural-only conversion, a single successful fixture,
or one successful compiler build does not satisfy this goal.
