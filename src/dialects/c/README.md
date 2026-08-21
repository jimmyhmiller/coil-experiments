# Native C reader (experimental)

This package is a whole-program C11 reader. At metaprogram time it runs clang's
preprocessor and semantic analyser (`-fsyntax-only -Xclang -ast-dump=json`) and
lowers the typed AST to ordinary Coil. It does **not** ask clang to generate code,
embed/link a C object, or retain an AST interpreter or runtime dispatch loop. The
Coil output is inspectable and Coil's normal native backend creates the binary.

```sh
coil run experiments.c.lang tests/c/fib.c       # inspect generated Coil
coil build tests/c/fib.c --use experiments.c.lang -o /tmp/fib
/tmp/fib
```

Multiple C translation units use the linkage-aware build driver:

```sh
python3 scripts/c-build.py src/main.c src/render.c src/game.c -o /tmp/game
```

Each source is preprocessed and type-checked by clang as an independent C
translation unit. The driver builds a program-wide symbol index, validates
external declarations, selects the owner of each tentative global definition,
gives `static` functions and globals unit-local identities, and then lowers the
units into one Coil native compilation. Compiling them together preserves Coil's
whole-program optimization and emits the runtime only once; it does not concatenate
C source or change preprocessing, tag, `static`, or tentative-definition scope.
`--cflag=-Iinclude` and `--cflag=-DFEATURE=1` pass preprocessing options, while
`--link-flag=-lSDL2` passes native libraries to Coil's final linker invocation.

The Python helper is parser glue only and must be run from the workspace root.
`clang` and `python3` are compile-time dependencies; produced executables need
neither. Includes and macros work because clang performs preprocessing first.

## Implemented surface

The reader lowers integer/floating scalar types with clang's resolved widths,
typedefs, enums, structs/unions, anonymous records, pointers, fixed arrays,
function pointers, direct/indirect calls, C/variadic externs, mutable parameters
and locals, arithmetic/comparisons/casts, lvalues, address and dereference,
indexing/member access, conditionals, switch/fallthrough, loops, break/continue,
goto/labels, and return. Static/global storage has native process lifetime and
zero initialization. Function-local cells are allocated once at function entry,
matching C's reusable automatic storage and allowing LLVM's normal mem2reg pass.
Scalar memory operations use Coil's explicit alias-aware load/store primitives to
carry C's strict-aliasing contract into LLVM TBAA metadata. Union member accesses
remain untagged so legal C union punning stays conservative.

Whole-program compilation specializes a C-defined variadic forwarding function
for each statically observed argument signature. This makes clox's
`runtimeError(...)/vfprintf` path fixed-signature ordinary Coil while preserving
external C variadics such as `printf` through Coil's C ABI support.

## Explicit limitations

This is not yet a conforming TCC-scale C implementation. Bitfields, VLAs,
atomics, GNU extensions, complex numbers, TLS, arbitrary irreducible goto graphs,
and packed/over-aligned layouts are not complete. Unions use
overlaid member access on storage whose ordinary Coil struct supplies sufficient
size/alignment for the validated corpus. Diagnostics name the first unsupported
typed-AST node instead of silently invoking C codegen.

The checked corpus includes three independent real applications: 4,979 lines of
clox, 3,206 lines of cJSON, and 2,848 lines of LZ4. clox passes all 246 vendored
Crafting Interpreters tests. cJSON parses, traverses, prints, and frees a document.
LZ4 repeatedly compresses and decompresses 8 MiB and verifies every byte.

## Language coverage baseline

`scripts/c-conformance.py` fetches immutable TinyCC and c-testsuite revisions into
the ignored `build/conformance` cache, compiles each applicable test through this
reader, executes it natively, and compares its ordered stdout/stderr with upstream
expectations. Unsupported C features count as failures. Explicit skips are limited
to platform assembly, TCC-only extensions and harnesses, upstream source/expectation
mismatches, invalid tests that TinyCC itself skips, and linker/multi-translation-unit
tests outside this single-source harness. Multi-unit behavior is covered separately
by `scripts/c-multi-unit.py`.

The current [full baseline](../../../tests/c/conformance/BASELINE.md) is 301/325
(92.6%) overall: 205/219 (93.6%) for portable c-testsuite cases and 96/106
(90.6%) for TinyCC's broader native regression corpus. These are frozen-corpus pass
rates, not a claim of ISO C conformance.

```sh
python3 scripts/c-conformance.py --suite all \
  --write-report tests/c/conformance/BASELINE.md
```

## Validation and comparison

```sh
python3 src/dialects/c/c_ast_to_coil.py tests/c/fib.c > /tmp/fib.coil
python3 scripts/c-multi-unit.py
python3 scripts/c-dialect.py
```

The script builds every case through both `clang -O3` and the Coil reader/native
backend, checks exact observable output, runs clox's 246-test suite, and measures
warmed clox and LZ4 application workloads. The current validation run measured
clox at 1.01× and LZ4 at 0.99× the matching Clang time. The gate rejects either
Coil-generated program exceeding Clang by more than 15%.
