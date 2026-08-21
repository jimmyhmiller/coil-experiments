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

The first end-to-end slice lowers integer/floating scalar types with clang's
resolved widths, typedefs, enums, named structs and fields, pointers,
fixed arrays, function pointers, direct/indirect calls, C/variadic externs,
mutable parameters and locals, arithmetic/comparisons/casts, lvalues, address and
deref, indexing/member access, conditionals, loops, break/continue, and return.
Static/global storage has native process lifetime and zero initialization.

## Explicit limitations

This is not yet a conforming C implementation. Designated/nested/global aggregate
initializers, unions, bitfields, anonymous records,
switch/goto/labels, VLAs, atomics, complex numbers, TLS, GNU statement expressions,
and exact signed/unsigned usual-arithmetic-conversion insertion remain unsupported.
Struct layout currently relies on Coil matching the target C ABI; packed/aligned
attributes are not represented. Local fixed-array and named-record positional
initializers are applied; designated, nested, and global aggregate initializers
remain unsupported. `static` local identity and C's
tentative-definition/coalescing rules are incomplete. Diagnostics deliberately
name the first unsupported typed-AST node instead of silently invoking C codegen.

Consequently clox and other substantial C applications are milestone targets,
not claimed passing targets. All three fixtures under `tests/c` build with the
dialect and are compared byte-for-byte (output, diagnostics, and exit status) with clang.

## Validation and comparison

```sh
python3 src/dialects/c/c_ast_to_coil.py tests/c/fib.c > /tmp/fib.coil
python3 scripts/c-dialect.py
```

The script verifies that translation succeeds, that no object/embedded-C escape
hatch appears, optionally builds/runs with `coil`, and reports size and elapsed
time beside `clang -O2`. Performance numbers are intentionally local measurements,
not checked-in claims.
