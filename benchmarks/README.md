# React HIR frontend benchmarks

## Large shared-subset comparison

`react-hir-direct-large.coil` and `oxc-parser-benchmark/src/main.rs` use the
same 165,000-byte, semantically valid ECMAScript module. Each repeated function
declaration lives in an independent block scope, so Oxc's semantic diagnostics
must remain empty; this is not an error-path benchmark.

Run the Coil text-to-SSA/CFG frontend benchmark with:

```sh
COIL_COMPILER=/path/to/simd-capable/coil \
  benchmarks/run-react-hir-direct-large.sh
```

Run the local Oxc comparison with:

```sh
OXC_DIR=/path/to/oxc benchmarks/run-oxc-parser-comparison.sh
```

The Oxc runner reports three relevant endpoints:

- parse only: source text to Oxc AST;
- parse + semantic: AST plus syntax checks, scopes, symbols, and references;
- parse + semantic + CFG: the preceding endpoint plus Oxc's optional CFG.

The Coil `text-to-ssa` endpoint includes scanning, direct parsing, lexical
scopes/bindings/references/captures, CFG construction, and SSA-valued IR. Oxc's
CFG endpoint is therefore closer than parse-only, but still does not construct
the SSA-valued IR produced by Coil.

At the time this benchmark was added, generic SIMD types required Coil's
`simd-foundation` branch (`d51cfcc`, containing `cbb723f`). That work was not yet
an ancestor of Coil `main`, so a compiler installed from `main` could not build
this benchmark.
