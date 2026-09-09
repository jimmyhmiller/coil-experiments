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

All bitmap-producing entry points accept an explicit valid byte count. SIMD
tail fill bytes therefore cannot appear as source events. Tape writes report
unconsumed bits when the destination capacity is exhausted.

The executable grammar now accepts `const`/`let`/`var` declarations; function
declarations and parameters; blocks; return, if/else, while, and expression
statements; identifiers, integer-shaped number spans, escaped quoted strings,
unary expressions, assignment, arrays, objects and properties, member access,
calls, conditionals, and generated longest-match compound binary operators;
plus self-closing and nested JSX, JSX text, expression children, and string or
expression-valued attributes. The focused broad regression combines all of
these constructs.

```js
const result = condition ? foo(a + b) : <Component value={x} />;
```

The remaining explicit frontier includes template `${...}` transitions, regexp
literals, complete numeric and operator syntax, automatic semicolon insertion,
declaration lists/destructuring, for/do/switch/try/class/import/export/arrow and
async/generator forms, optional/computed access, spreads, TypeScript, Unicode
identifiers, scope construction, recovery, and the final React compiler HIR
schema.

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
