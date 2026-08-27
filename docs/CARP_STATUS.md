# Carp compatibility status

This document defines what “90% Carp compatibility” means for the Carp dialect.
It is a measured conformance target, not a feature checklist or an estimate.

## Oracle and pinned inputs

The compatibility oracle is the upstream `carp-lang/Carp` test corpus. The
initial pinned checkout is:

```text
ea121b5a62163dc872a4b2c4f3ad151fb0f5b8df
```

`cyberwitchery/metacarp` is the phase-by-phase implementation reference. The
initial pinned checkout is:

```text
064e206bea5925934bf7f6d6abf8f9ce378d13f6
```

The checkouts live beside this repository as `carp-upstream` and
`metacarp-upstream`; they are reference inputs and are not vendored production
dependencies.

## Compatibility metric

The corpus is divided into executable-output tests, ordinary executable tests,
expected-rejection tests, and compile-only tests. A selected entry passes only
when the Coil implementation produces the expected observable outcome:

- output tests must build, run successfully, and match the expected bytes;
- ordinary tests must build, run, and exit successfully;
- rejection tests must be rejected during compilation;
- compile-only tests must produce a linkable executable.

The score is `passes / selected entries`. Skips, crashes, timeouts, unsupported
features, and known gaps remain in the denominator and are not passes. The
headline score is reported together with category totals so a compiler cannot
reach the target by accepting programs while failing rejection tests.

The initial corpus definition follows `metacarp/scripts/run-carp-suite-self.sh`.
Against the pinned Carp checkout its globs select 163 entries: 20 exact-output,
76 ordinary run, 50 expected-rejection, 16 ordinary build, and one no-core
build. Metacarp's README still says 154, so that number is stale. The exact 163
paths are frozen in `tests/carp/corpus.tsv`; upstream changes must therefore be
reviewed rather than silently changing the denominator.

## Required semantic pipeline

The implementation is production Coil code and does not invoke Python. Python
may drive the external test corpus only.

```text
source-located Carp reader
  -> deterministic module/load graph
  -> compile-time environment and macro evaluation
  -> expansion
  -> name and interface resolution
  -> Hindley-Milner inference
  -> specialization / monomorphization
  -> flow-sensitive ownership and borrow checking
  -> cleanup, move, and borrow plan
  -> ordinary hygienic Coil syntax emission
  -> the normal Coil compiler
```

Ownership compatibility includes rejection behavior, not merely inserted
destructors. The checker must account for moves, local borrow escape,
borrow-after-move, control-flow joins, mutation, shared-lifetime accessors, and
by-value pattern bindings. Cleanup planning must cover parameters, lexical
bindings, discarded owned temporaries, overwritten values, match payloads, and
branch exits without double deletion.

## Current state

The upstream repositories and their exact revisions are recorded. A verified
corpus runner lives at `scripts/carp-progress.py`; it preserves individual logs
and a JSON report, applies timeouts, checks output byte-for-byte, and never
counts skips or known gaps as passes. The first production phase library,
`experiments.carp.graph`, ports metacarp's strongly-connected-component ordering
and is covered by focused Coil tests. The production type solver now covers
recursive monotypes, nominal constructor variables, lifetimes, structural and
representation equality, variable-chain resolution, occurs checking, and
unification. The ownership state engine covers local/parameter/static/external
origins, origins with multiple possible owners, branch joins, moves,
reassignment, local escape, and borrow-after-move. `coil test --suite carp`
now exercises the typed specialized IR and its flow-sensitive expression
analyzer as well: lets, sequences, mutation, branches, loops, matches,
left-to-right call evaluation, delayed by-value moves, direct borrows, and
shared-lifetime call results. The ownership planner adds any-path/all-path
consumption analysis, rejects
duplicate stable expression identities, schedules binding/parameter/discarded-
temporary cleanup, records alias moves, handles self-rebinding, and deduplicates
delete-function requirements by runtime representation. The Carp phase gate now
also includes a source-located Carp reader. It retains comments, recognizes
lists, arrays, static arrays, dictionaries, numeric/boolean/character/string/
pattern/symbol forms, handles qualified symbols and raw strings, expands all
seven Carp reader macros, and diagnoses malformed delimiters, strings, symbols,
and reader-macro spacing. Exact source spellings and byte/line/column bounds are
preserved for later diagnostics and literal lowering. The Carp phase gate now
passes all 54 tests, including under per-file `--debug-checks` builds.

The reader now feeds `experiments.carp.forms`, a separate semantic surface
boundary that decodes numeric, floating, character, ordinary/raw string, and
pattern values exactly once; splits qualified names into segments; recursively
lowers collections; and attaches the originating source identity to every span.
Regression coverage includes Carp's deliberately unusual digit-string escape
behavior and UTF-8 character literals. The compile-time environment uses stable
frame and cell IDs, supports lexical parents, shared mutable aliases, explicit
imports, shadowing, and ambiguity detection without retaining pointers into
growable frame storage.

The Coil-native `experiments.carp.frontend-check` audit executable successfully
reads and semantically lowers every source path in the frozen corpus: 163/163.
This is a front-end coverage gate only and is deliberately not accepted by the
compatibility outcome harness as a compiler.

One upstream `carp-reader` 0.4.1 defect was found while running that gate. Its
number parser commits any `0b` prefix to binary before checking for a following
binary digit, so Carp's ordinary zero-byte literal `0b` fails numeric parsing
and falls back to a symbol. The pinned Carp corpus uses `0b` in
`examples/benchmark_mandelbrot.carp`. This implementation disambiguates by
treating `0b` as the byte-suffixed decimal zero and only selecting binary when
at least one binary digit follows the prefix.

`experiments.carp.module` now performs deterministic, pure module loading over
a caller-supplied source registry. It recursively splices `load`, deduplicates
canonical files reached through alias paths, detects active-stack recursion,
normalizes `core/` load paths, translates `load-and-use` into a post-load
`use-all`, brackets every file with compile-time load-stack markers, and keeps
the original file identity in every node span. Generated syntax is cloned and
can be recursively reanchored without mutating its input. The Carp phase gate
now includes a stable-cell compile-time evaluator and source-ordered macro
expander. The evaluator supports lexical and returned closures, mutation,
sequential `let`/`let-do`, `do`, `if`, `and`/`or`, bounded `while`, `for`,
quotation/evaluation/parsing, rest parameters, scalar arithmetic/comparison,
UTF-8 string-to-collection conversion and character-indexed string slicing,
structural quasiquotation/unquotation/list splicing, lazy `case`, list boundary
operations, symbol construction/qualification, variadic `str`, explicit host
configuration, and source-spanned failure with a fuel limit. Array
unquote-splicing is rejected to match the reference implementation. Macro and
dynamic definitions share that evaluator; definitions are omitted from runtime
syntax, calls receive syntax values, results are reanchored and recursively
expanded, and quoted forms remain opaque. Mutual dynamic recursion resolves
through the shared environment at call time.

Expansion now uses module-scoped compile-time frames. Qualified dynamic names
and imported names alias the same stable cell, reopened modules retain state,
ambiguous imports fail, and source-ordered runtime bindings shadow macros
without hiding compile-time primitives that share runtime interface names.
With explicit `arm64`/`macos`/`native` audit configuration, the pinned upstream
`core/Core.carp` plus its full source registry expands successfully to 461
runtime forms. The earlier 558 count included 94 internal load-stack markers
and three top-level dynamic calls; those are now consumed by expansion as the
compile-time operations they are.

`experiments.carp.resolve` now resolves that complete expanded Core module. Its
two-pass collector supports forward recursion, reopened and nested modules,
parent-relative qualified names, imports, source redefinition with stable
identity, registered and ordinary struct constructors/readers/setters/updaters,
algebraic constructors with bare and type-qualified aliases, interfaces,
templates, and the pinned metacarp primitive registry. Lexical binders receive
stable negative identities. Same-arity qualified overloads are preserved as
explicit candidate sets for type inference rather than guessed during name
resolution. The Core resolution audit currently emits 1,428 unique global
identities. Resolved modules now retain builtin, template, interface, and
definition signatures—including signatures represented by expanded `meta-set!`
forms—and synthesized algebraic-constructor signatures. The first inference
boundary converts all 725 signatures in expanded
Core into reusable polymorphic schemes with separately quantified type and
lifetime variables; instantiation freshens every use while preserving sharing
within one signature. Registered struct fields are included as synthesized
accessor, setter, mutator, and updater signatures. Generated standard operations
are retained without overriding explicit source definitions.

The Carp phase gate is 130/130 normally across all Carp test modules. The
separate front-end audit remains 163/163, and `git diff --check` passes. Core
expansion and name resolution are now verified gates. Expression inference is
active across all of expanded Core: the audit resolves 1,428 globals, converts
725 signatures, and infers 2,334 calls. It now includes retained
interface-to-implementation edges, deferred overload constraints,
constraint-aware polymorphic generalization, exact-before-implicit-borrow
overload ranking, directional implicit borrowing,
top-level value inference, distinct pattern-literal typing, and exact schemes
for several compiler-owned Array templates. Of 1,009 overload sites, 294 are
concrete during module inference and 715 remain deferred until specialization.
The specialization phase now preserves literal, array, and pattern payloads;
selects deferred overloads from a concrete instantiation; retains typed pattern
bindings; and follows concrete user-function calls with a deduplicating
monomorphization worklist. For reached concrete types, exact `delete` and `blit`
implementation signatures now determine ownership facts. A semantic gate
borrow-checks each specialized function and creates its cleanup/move/borrow plan
before emission. The registered reader provider now executes this pipeline at
Coil compile time and returns hygienic ordinary Coil `Code`; a no-Core Carp
program passes through the normal Coil compiler. Full-module roots, top-level
values, ownership-action emission, and substantial runtime data/control forms
remain incomplete. There is deliberately no Carp-specific C backend.

The first complete executable-corpus baseline is 52/163 (31.90%): 0/20 output,
0/76 run, 50/50 rejection, 1/16 build, and 1/1 no-Core build. Rejection passes
currently prove only that compilation rejects the program, not that every case
reaches Carp's intended diagnostic, so they are not evidence of broad semantic
completeness. The current full-Core executable probe gets past numeric `sign`
overload specialization after fixing premature generalization, and next stops
while inferring `Array.=` because nested `defndynamic` calls such as `/=` still
need the reference compiler's full dynamic-expansion semantics. No 90%
compatibility claim is warranted until the corpus runner itself measures it.

Two duplicate declarations were observed in the pinned upstream Core sources:
`core/Interfaces.carp` declares the `mod` interface twice with the same
signature, and `core/String.carp` defines `StringCopy.str` twice at the same
arity with different bodies. Carp's interactive redefinition semantics keep a
single global identity and make the later definition authoritative, so the
resolver preserves ordered definitions under one interned identity.

The pinned Carp 0.6.0 checkout now builds successfully with Stack and provides a
current arm64 reference executable. `CARP_DIR` is set to the checkout root for
differential runs. The reference accepts `test/int_math.carp`; a reachable
`Array.=` probe shows that Carp specializes the compile-time `/=` definition
into ordinary typed functions such as `/=__Int` and `/=__&Int`, while unused
`Array.=` does not participate in checking `int_math`. This is evidence that the
remaining implementation must support demand-driven definition inference and
static specialization of dynamic functions, rather than eagerly rejecting an
unreachable Core definition or hard-coding `/=` as an Int primitive.

The corpus harness now supports the current Carp 0.6 CLI without the removed
`-c`/`-o` flags: each build receives an isolated configured output directory,
programs execute from the Carp checkout so relative fixtures resolve, current
`--check` diagnostics count as rejection even though Carp exits zero, and the
produced executable is verified. A four-category reference smoke manifest
passes 4/4. The first corrected full reference pass reached 157/163 (96.32%);
its six misses were harness-environment cases found before the final working-
directory fix plus the intentionally empty rejection input. The frozen corpus
therefore demonstrably contains enough reference-passing cases for the 90%
target; Coil's measured score remains 52/163 until its next full rerun.
