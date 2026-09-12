# React HIR frontend experiment

This workspace member is an executable path toward parsing JavaScript/JSX
directly into the semantic structures needed by React HIR.

The implemented pipeline is:

1. `dsl.coil` provides the primitive byte-class expression compiler.
2. `program.coil` compiles a complete named classification graph, including
   shared predicates and a requested output projection, into one fused generic
   `coil.simd` bitmap kernel. Large byte sets become compile-time nibble tables;
   compatible sets share one tagged lookup when eight tag bits suffice.
3. `structural.coil` specifies the JavaScript graph once and produces
   width-independent scalar bitmaps from the generated kernel.
4. `lexical.coil` uses SIMD to build a bitmap of state-changing bytes, visits
   only mode-relevant sparse events, and assigns the ordinary spans between
   them in one operation. Chunks with no possible transition bypass the event
   loop. It carries quote, escape, line-comment, and block-comment state across
   chunks. A retained scalar implementation is the differential oracle; a
   one-byte overlap resolves comment openers at boundaries.
5. `frontend.coil` shields structural events inside strings and comments. Its
   fastest logical 64-byte kernel uses two physical 32-byte SIMD vectors.
6. `tape.coil` stably compacts visible events into caller-owned position/kind
   arrays without imposing an allocation strategy. The full-capacity path uses
   sparse bitmap iteration and compile-time tag bitplanes.
7. `pipeline.coil` is the complete buffer API: it scans bulk 64-byte chunks,
   handles the safe partial tail, carries state, and materializes the tape.
   It offers split position/kind arrays and a faster checked packed `u32` event
   layout whose low three bits hold the kind and whose upper 29 bits hold the
   file-relative position. Inputs at or above 512 MiB report overflow before
   writing and can use the unrestricted split layout.
   A grammar-oriented packed variant additionally emits only lexically valid
   single/double-quote boundary events, keeping string contents sparse while
   enabling lazy literal parsing.
8. `frontend_spec.coil` is the single readable language definition for the
   implemented parser slice. It declares named terminals, precedence groups,
   primary/postfix dispatch, and complete production shapes.
9. `grammar.coil` implements `def-frontend-grammar`. The compile-time
   metaprogram validates references and shapes, assigns stable symbolic ids,
   and emits specialized terminal, keyword, form, precedence, and production
   queries. There is no runtime grammar table or initialization.
10. `parser.coil` consumes those generated queries and packed events while
   lazily reading spellings and operator bytes from the immutable source. It
   contains cursor, arena, Pratt-loop, list, and semantic-construction
   machinery rather than duplicated language spellings. It writes source-backed HIR nodes
   directly into caller-owned structure-of-arrays storage, with linked edge
   records for variable-length child lists. No token array, CST, or JavaScript
   AST is constructed.
11. `ir.coil` defines the target semantic IR independently of the temporary
    syntax arena: regions, basic blocks, block parameters, operations, SSA
    results and operands, explicit terminators/successors, nested-region
    ownership, scopes, bindings, references, captures, and source spans. Its
    verifier checks structural ranges, terminator placement, successor arity,
    reciprocal region/value ownership, same-region CFG edges, same-block
    definition order, and cross-block dominance using a scalable caller-owned
    bitset. Its capacity-safe native printer emits deterministic textual IR.
    `ir_test.coil` exercises a real diamond CFG whose branch-local values merge
    through a join block parameter, plus negative arity and dominance cases.
12. `ir_builder.coil` is the allocation-free direct-construction API intended
    for parser actions. Parsing may interleave parent operations with blocks,
    operations, and regions nested beneath them. Intrusive staging links are
    compacted into stable handle pools in one linear finalization pass; no AST
    is materialized. `ir_builder_test.coil` constructs such an interleaved
    nested program, including lexical binding/reference/capture identities,
    verifies it, and checks its exact textual IR.
13. `ir_storage.coil` maps one aligned caller-owned byte buffer into every IR
    and builder plane from explicit capacities. `direct_parser.coil` is the
    first real AST-free text-to-SSA path: it consumes the SIMD parse tape and
    directly emits literal/identifier/unary/binary/call/member/array/object/property/
    assignment/declaration/
    expression/return operations, SSA operands/results, lexical bindings/
    references/captures, functions with nested regions, and final terminators.
    Non-computed member properties retain their source name on the member op
    without becoming lexical identifier references.
    Caller-owned scratch preserves variable-length call operands without an AST
    and supports nested calls, arrays, and objects. Object properties are
    source-named SSA operations consumed by their object operation, so property
    identity is retained without a syntax node. `direct_parser_test.coil` runs that complete path,
    verifies the result, and checks deterministic textual IR including packed
    operator immediates and declaration/function-name metadata. Direct `if`
    statements now build
    condition, branch, and merge blocks with explicit successors. Direct
    `while` statements build entry, header, body, and exit blocks with a real
    backedge; the cyclic graph passes dominance verification. Conditional
    expressions additionally merge their branch values through a join block
    parameter and successor arguments.
14. `js_printer.coil` regenerates normalized JavaScript for the implemented
    subset by following SSA definitions and nested function regions rather than
    retained syntax nodes. The regression suite proves JavaScript
    text-to-IR-to-JavaScript-to-IR stability for operation kinds, compact
    attributes, operands, SSA counts, regions, blocks, scopes, bindings,
    references, and captures while allowing source locations to change under
    formatting.
15. `ir_text_parser.coil` is the inverse of the native IR printer. It reads the
    canonical text directly into `IrBuilder`, predeclaring blocks per region so
    forward CFG edges need no syntax tree. The textual form now retains source
    size, parent and nested-region ownership, compact operation attributes,
    scopes, bindings, references, and captures. Byte-identical print/parse/print
    tests cover a CFG with a join block parameter, a parsed multi-block
    statement CFG, and nested regions with lexical capture metadata.
16. `parser_generator.coil` is the semantic parser-generator layer. Every
    construct parser is emitted at Coil compile time; `direct_parser.coil`
    defines no `parse-` function of its own, only the cursor, UTF-8, span,
    binding, and scratch primitives a generated parser calls.

    The grammar in `frontend_spec.coil` determines the parser, not just its
    byte constants. `def-frontend-grammar` emits a `NAME-production-steps`
    accessor per production holding the normalized step vector, with terminal
    and separator names already resolved to bytes; the generator splices it in
    at expansion time and walks it in order. 26 of the 33 strategies that once
    indexed a fixed step position now do this, across 51 declared productions.
    Deleting the parentheses from `while-production` yields a working parser for
    `while cond { ... }`; renaming a clause keyword, re-spelling a list
    separator, or re-bracketing a destructuring pattern all move the parser with
    the grammar. Roles claim `(rule X)`, `(repeat X)`, `(separated X B)` and
    `(terminator B)` steps by name, and a production that no longer supplies a
    role its strategy needs is a hard expansion error, never a silently broken
    parser.

    `(terminator BYTE)` marks an ASI-eligible statement end, routed through the
    statement-end parser rather than consumed as a plain byte. `javascript-asi`
    itself stays a primitive - ASI is a rule *about* productions, not a step
    sequence - but both spellings it tests are now derived from the productions
    it must agree with, so the block parser and ASI cannot disagree about where
    a block ends.

    `benchmarks/check-grammar-authority.sh` proves this by perturbing the
    grammar, rebuilding, and asserting the parser followed: six cases covering
    undelimited `while`, a renamed `else`, renamed `do`/`while` keywords, a
    re-spelled type annotation, try/catch keywords and catch delimiters, and a
    production missing a required role, which must fail to compile.
    `benchmarks/compare-against-baseline.sh REF` is the behavioural gate: it
    builds the checker at `REF` in a scratch worktree and requires byte-identical
    textual IR on all 70 valid fixtures and identical diagnostics on all 131
    invalid ones. The whole migration is byte-identical to the pre-migration
    commit, at unchanged throughput.

    Nine indexed uses remain, and each is a site borrowing a byte from a
    production that describes a different construct - the `=` of `=>` and of a
    destructuring default taken from `assignment-production`; a declarator-list
    comma taken from `call-production`; an interface body's `{` taken from
    `block-production`; a FOLLOW-set member for type-argument lookahead. These
    are deliberately not migrated: walking an unrelated production's shape is
    what produced the original coupling. Each needs its own declaration - an
    arrow production, a binding-initializer production, an object-type
    production - or, for the FOLLOW set, a notion of first/follow sets the
    grammar does not yet have.

    The generator is still one `compile-` function per construct. Only
    `terminated-expression`, `structured-type-span`, `separated-value`,
    `control-transfer` and `class-parameter` are shared across more than one
    production. Collapsing those one-off strategies into general forms is the
    remaining half of the work; making the shapes authoritative was the first.

All bitmap-producing entry points accept an explicit valid byte count. SIMD
tail fill bytes therefore cannot appear as source events. Tape writes report
unconsumed bits when the destination capacity is exhausted.

The executable grammar now accepts initialized and comma-separated
`const`/`let`/`var` declarations, plus uninitialized `let`/`var`; function
declarations and parameters; blocks; valued and empty return, empty, debugger,
if/else, while, and expression statements; identifiers, boolean and null
literals, `this`, integer-shaped number spans, escaped quoted strings,
unary expressions, assignment, arrays, objects, named and shorthand properties, member access,
computed member access,
calls, conditionals, and generated longest-match compound binary operators;
single-parameter and parenthesized block- or expression-bodied arrow functions;
plus self-closing and nested JSX, JSX text, expression children, and string or
expression-valued attributes. Focused source fixtures also verify that CFG
fallthrough after `if`, `while`, and conditional expressions is terminated on
the active join/exit block.

```js
const result = condition ? foo(a + b) : <Component value={x} />;
```

The remaining explicit frontier is tracked by the feature inventory in
`pad://react-hir-frontend`, independently of corpus acceptance. The largest
unimplemented structural families are Unicode whitespace/line-terminator
handling, script-mode `with`, remaining JSX/TSX ambiguity and lexical edges, contextual
early errors, recovery, and the final React compiler HIR schema. Generated
paths now cover the principal CFG statements, structured try/catch/finally,
async/generator function declarations, expression-bodied and async arrows,
optional/computed access, spreads, regexps, numeric forms, and ASI.
They also cover source-named labeled statements and labeled `break`/`continue`
with CFG-resolved targets, structured TypeScript declarations and modules,
resource declarations, tagged templates, dynamic imports, and meta properties.
Raw UTF-8 identifiers use the exact Unicode 15.1 ID_Start/ID_Continue tables
used by Oxc, including astral code points, combining continuations, and the
ECMAScript ZWNJ/ZWJ additions. The SIMD scanner treats non-ASCII bytes as a
candidate word run and invokes UTF-8/table validation only on the parser's
cold non-ASCII path. Fixed and braced Unicode identifier escapes are decoded
against the same tables. Canonical code-point hashing and equality make escaped
and raw spellings one binding or label identity while retaining original source
spans; malformed escapes, escaped reserved words, and duplicate canonical
labels are permanent negative fixtures.

The SSA/CFG schema, direct builder, verifier, printer, and a working direct
parser slice exist. The broader legacy `parser.coil` coverage has not yet been
migrated, and the parser benchmark still measures its syntax arena rather than
text-to-verified-SSA throughput. The next coverage work is collections, member
access variants, richer property forms/spreads, JSX, and structured printing for multi-block
CFGs. As in JSIR's current JavaScript dialect, expression results have SSA
identities while mutable bindings remain explicit l-value/assignment semantics;
the generic block-argument machinery is used when values genuinely merge.
The JavaScript semantic round-trip gate now covers linear expressions and
functions with lexical captures, and the
canonical textual-IR round-trip gate now passes for CFG and nested semantic
fixtures. `benchmarks/run-jsir-differential.sh` runs the first live structural
differential against the local `jsir-rs` frontend: both independently parse a
shared fixtures and must emit the same backend-neutral semantic signature. The
current fixture includes a declaration, loop, binary mutation, assignment,
identifier reads, member access, nested array/object aggregates, and a call;
Coil derives the loop count from CFG backedges
while JSIR reports its structured while operation. Broader differential
fixtures remain open.

## IR correctness gates

`ir/verify-ir` is the authority for whether a successfully constructed arena
is internally valid. It runs ordered phases so no later phase indexes through
an unchecked identity or range:

1. region, block, operation, operand, result, successor, child-region, and
   source-span bounds;
2. exact ownership of every dense block, operation, value, and nested region;
3. terminator placement and opcode-specific control-flow cardinality;
4. same-region successor targets, successor-argument arity, and independent
   entry reachability (including rejection of disconnected cycles);
5. fixed-point dominators, definition identity, same-block definition order,
   cross-block dominance, and successor-argument uses;
6. nested scope spans, bindings, references, and captures.

The verifier returns a compact `VerifyResult` containing an error code and the
most specific region, block, operation, and plane index available. The
`react-hir-check` corpus executable runs it after every successful parse and
uses a distinct exit status for parse and verification failures. Benchmarks do
not include verifier time unless their name explicitly says `verified`.

`ir_test.coil` contains a valid SSA diamond and mutation-based negative cases
for successor arity, non-dominating uses, duplicate/missing block, operation,
and value ownership, malformed control-flow opcodes, and unreachable blocks.
`direct_parser_test.coil` additionally verifies source-derived CFG/scope IR and
canonical IR print/parse/print stability. `run-jsir-differential.sh` supplies an
independent structural oracle for the currently shared JSIR subset. Passing
these gates establishes structural validity and cross-implementation agreement;
it does not by itself prove complete JavaScript observational equivalence.

The SIMD frontend requires the combined compiler at Coil branch
`simd-foundation` commit `d51cfcc` or later. That revision includes both generic
SIMD support and typed narrow-integer constant lowering. Older artifacts emit
invalid LLVM call signatures for these constants; their ARM backend can instead
produce ABI-corrupt behavior that appeared as overwritten fixture storage.

## Benchmark

The benchmark accepts an optional source file. It compiles a separate C memory
barrier so LLVM must preserve every tape store without adding a checksum walk to
the timed region:

```sh
COIL_COMPILER=/path/to/coil benchmarks/run-react-hir-frontend.sh corpus.tsx
```

Without a path it uses the built-in 1 MiB synthetic source. File measurements
run the full-width bulk prefix; a production call to `scan-source-to-tape64`
also processes the at-most-63-byte tail. On the local Apple M2 Max, the
235,245-byte shadcn TSX corpus reaches a five-run median near 1.12 GB/s for the
fully materialized split source-to-tape pipeline and about 1.18 GB/s for the
packed layout.

`benchmarks/run-react-hir-parse.sh` measures the real parser slice over a
supported repeated program. On the local Apple M2 Max, the initial implementation
measured about 0.72 GB/s for packed-tape-to-HIR and 0.40 GB/s for complete
text-to-packed-tape-to-HIR. After the coverage expansion above, a five-run
checkpoint measures 0.588 GB/s for parse-tape-to-HIR and 0.338 GB/s end to end.
The additional cost includes compound-operator lookahead and the literal-aware
parse tape; it is retained honestly rather than benchmarked through the former
narrow path. This remains a language subset and is not yet semantically
comparable to Oxc's full JavaScript/TypeScript parser.

`benchmarks/run-react-hir-direct-large.sh` measures the generated direct
frontend on a 161,000-byte application-shaped JavaScript file covering
functions, lexical bindings, arithmetic/comparison, loops, conditionals,
calls, members, arrays, objects, returns, scopes, and captures. It reports
prepared-tape-to-SSA separately from complete text-to-SSA. The matching
`benchmarks/run-oxc-parser-comparison.sh` parses identical bytes with the local
Oxc checkout (`OXC_DIR` overrides its location).

### Throughput, and what it is fair to compare against

Measured on the local Apple M2 Max, same 165,000-byte fixture, same 100 rounds,
best of nine runs. The Oxc harness reports four modes and they do very different
amounts of work, so the mode chosen decides the answer:

| what it produces | GB/s |
| --- | --- |
| Coil text-to-SSA — SSA, CFG, blocks, scopes, bindings, references, captures | 0.119 |
| Coil prepared-tape-to-SSA — the same, minus the scan | 0.138 |
| `oxc cold parse` — AST only | 0.191 |
| `oxc reset+parse` — AST only, reused allocator | 0.176 |
| `oxc parse+semantic` — AST, scopes, symbols, references | 0.076 |
| `oxc parse+semantic+cfg` — the above plus a control flow graph | 0.063 |

Against the Oxc mode whose output is comparable to ours, Coil is about 89%
faster. Against Oxc's AST-only parse, Coil is about 38% slower while also
building SSA, a CFG, scopes, bindings and captures that the AST parse does not.
An earlier revision of this file compared our full semantic output against Oxc's
AST-only number and reported Oxc as 27% faster; that was the wrong row.

Two further asymmetries are worth stating rather than buried. The Oxc harness
parses with `SourceType::mjs()`, so it is parsing JavaScript only, while this
frontend carries JavaScript, TypeScript and JSX in one path and checks for type
annotations and assertions on input that has none. And this frontend still
accepts a narrower grammar than Oxc overall. Neither number is full-language
equivalence in either direction.

### Where the time goes

`benchmarks/compare-against-baseline.sh REF` builds the checker at a baseline
ref in a scratch worktree and requires byte-identical textual IR on all 70 valid
fixtures and identical diagnostics on all 131 invalid ones before reporting
throughput for both. Every optimisation below was required to pass it.

A floor measurement settles where optimisation effort is worth spending: moving
the cursor across every event in the tape and reading the byte it caches, with
no parsing and no IR construction, runs at about 1.25 GB/s. Tape traversal is
therefore roughly a tenth of parse time, and the remaining nine tenths are
parsing logic and IR construction. The tape representation is not the limit.

The release profile is flat. The SIMD scan is about 16%, the precedence loop
about 13%, and no other single function exceeds 6%; twenty-six functions cover
93%. Optimisation at that shape yields a few percent at a time, and several
attempts yielded nothing measurable because LLVM had already performed them —
restructuring the operator table into first-byte switches, deduplicating repeated
byte loads, and sinking arena loads behind cheaper guards each measured zero in
an A/B over nine runs.

### A throughput regression that coverage expansion introduced

Commit `cd3012b` measured 0.173 GB/s tape-to-SSA and 0.144 GB/s text-to-SSA,
matching the figures this file used to quote. Ninety-seven commits of coverage
expansion later, `a26dcc2` measured 0.093 and 0.085 — a loss of about 40% that
no single commit caused. Sampling nine points across that range shows a gradual
slide (0.142, 0.103, 0.124, 0.117, 0.106, 0.103, 0.104, 0.101, 0.084), so bisect
finds only noise. The optimisations above recovered part of it, to 0.138 and
0.119, which is still below the `cd3012b` peak. Expanding coverage has a
throughput cost, and it is only visible if it is measured; the baseline
comparison script exists so the next expansion does not repeat this silently.

`benchmarks/run-jsir-differential.sh` requires `JSIR_RS_DIR` to point at a
`jsir-rs` checkout containing the `coil_signature` example (local commit
`5616a14` on the `coil-differential` worktree). It compares independent output,
not a checked-in golden:

```sh
COIL_COMPILER=/path/to/coil \
JSIR_RS_DIR=/path/to/jsir-rs benchmarks/run-jsir-differential.sh
```
