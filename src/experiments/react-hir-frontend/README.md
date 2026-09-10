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
16. `parser_generator.coil` begins the actual semantic parser-generator layer.
    A declarative `separated-value` production now generates the full direct
    array parser at Coil compile time: repetition, separators, caller-owned
    scratch lifetime, diagnostics, spans, and IR emission. The handwritten
    array parser was deleted, nested aggregate regressions pass through the
    generated function, and macro expansion exposes the generated Coil for
    inspection. Other productions remain handwritten until migrated through
    general generator forms rather than construct-specific parser additions.

All bitmap-producing entry points accept an explicit valid byte count. SIMD
tail fill bytes therefore cannot appear as source events. Tape writes report
unconsumed bits when the destination capacity is exhausted.

The executable grammar now accepts `const`/`let`/`var` declarations; function
declarations and parameters; blocks; valued and empty return, empty, debugger,
if/else, while, and expression statements; identifiers, boolean and null
literals, `this`, integer-shaped number spans, escaped quoted strings,
unary expressions, assignment, arrays, objects and properties, member access,
calls, conditionals, and generated longest-match compound binary operators;
plus self-closing and nested JSX, JSX text, expression children, and string or
expression-valued attributes. Focused source fixtures also verify that CFG
fallthrough after `if`, `while`, and conditional expressions is terminated on
the active join/exit block.

```js
const result = condition ? foo(a + b) : <Component value={x} />;
```

The remaining explicit frontier includes template `${...}` transitions, regexp
literals, complete numeric and operator syntax, automatic semicolon insertion,
declaration lists/destructuring, for/do/switch/try/class/import/export/arrow and
async/generator forms, optional/computed access, spreads, TypeScript, Unicode
identifiers, scope construction, recovery, and the final React compiler HIR
schema.

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

On the local Apple M2 Max, release builds measured approximately 0.180 GB/s for
Coil tape-to-SSA, 0.147 GB/s for Coil text-to-SSA, and 0.186–0.187 GB/s for Oxc
text-to-AST. Oxc is about 27% faster than Coil end to end on this shared-subset
fixture. Coil's result includes direct SSA values, CFG blocks and successors,
block parameters, bindings/captures, scopes, and finalized membership; Oxc's
measurement stops after AST parsing. These numbers are not full-language
equivalence because the Coil frontend still accepts a narrower grammar.

`benchmarks/run-jsir-differential.sh` requires `JSIR_RS_DIR` to point at a
`jsir-rs` checkout containing the `coil_signature` example (local commit
`5616a14` on the `coil-differential` worktree). It compares independent output,
not a checked-in golden:

```sh
COIL_COMPILER=/path/to/coil \
JSIR_RS_DIR=/path/to/jsir-rs benchmarks/run-jsir-differential.sh
```
