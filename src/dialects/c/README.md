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

Whole-program compilation specializes a C-defined variadic forwarding function
for each statically observed argument signature. This makes clox's
`runtimeError(...)/vfprintf` path fixed-signature ordinary Coil while preserving
external C variadics such as `printf` through Coil's C ABI support.

## Explicit limitations

This is not yet a conforming TCC-scale C implementation. Bitfields, VLAs,
atomics, complex numbers, TLS, GNU statement expressions, arbitrary irreducible
goto graphs, and every packed/over-aligned layout are not complete. Unions use
overlaid member access on storage whose ordinary Coil struct supplies sufficient
size/alignment for the validated corpus. `static` local identity and C's
tentative-definition/coalescing rules also remain incomplete. Diagnostics name
the first unsupported typed-AST node instead of silently invoking C codegen.

The checked corpus includes three independent real applications: 4,979 lines of
clox, 3,206 lines of cJSON, and 2,848 lines of LZ4. clox passes all 246 vendored
Crafting Interpreters tests. cJSON parses, traverses, prints, and frees a document.
LZ4 repeatedly compresses and decompresses 8 MiB and verifies every byte.

## Validation and comparison

```sh
python3 src/dialects/c/c_ast_to_coil.py tests/c/fib.c > /tmp/fib.coil
python3 scripts/c-dialect.py
```

The script builds every case through both `clang -O3` and the Coil reader/native
backend, checks exact observable output, runs clox's 246-test suite, and measures
warmed clox and LZ4 application workloads. It fails if either Coil-generated
program exceeds the matching Clang binary by more than 30%.
