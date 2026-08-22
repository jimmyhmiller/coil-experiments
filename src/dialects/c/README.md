# Native C frontend (experimental)

This package is a whole-program C11 frontend implemented in ordinary Coil.
Clang is invoked directly by argv to preprocess and type-check each source and to
emit its typed JSON AST:

```text
clang -std=gnu11 -fsyntax-only -Wno-everything \
      <C flags> -Xclang -ast-dump=json <translation-unit.c>
```

Clang never emits LLVM IR, assembly, objects, or executables in this build path.
`experiments.c.ast` parses the output through `coil.json`,
`experiments.c.build` establishes C linkage over independent translation units,
and `experiments.c.lower` emits one inspectable ordinary Coil program. Coil's
normal native backend compiles that generated program and contributes the
standard library once.

## Building C

`scripts/c-build.py` is only a thin bootstrap/invocation harness for the native
builder; it contains no frontend logic:

```sh
python3 scripts/c-build.py --compiler "$(command -v coil)" \
  tests/c/fib.c -O0 -o /tmp/fib
/tmp/fib

python3 scripts/c-build.py --compiler "$(command -v coil)" \
  src/main.c src/render.c -O0 -o /tmp/game \
  --cflag=-Iinclude --cflag=-DFEATURE=1 --link-flag=-lm
```

Pass `--build-dir DIR` to retain the generated `DIR/program.coil`, or
`--frontend-only` to stop after writing it. Without a build directory, the
generated file is removed after a successful full build. The native builder can
also be compiled and invoked directly:

```sh
coil build src/dialects/c/build.coil -O3 -o build/c-native/c-build
build/c-native/c-build tests/c/fib.c -O0 -o /tmp/fib --coil "$(command -v coil)"
```

## Translation units and types

Every C source is preprocessed, type-checked, indexed, and lowered as a separate
translation unit. There is no C source concatenation. The linker index validates
external function/global declarations, tentative and initialized definitions,
recursive record layouts, unit-local `static` identities, constructors and
destructors, and function reachability before lowering. C declarators are lexed
and parsed into recursive structural types: pointer/array/function precedence is
not inferred from regular expressions, token counts, or canonicalized strings.

The implemented corpus exercises scalar and aggregate values, enums, typedefs,
anonymous records, pointers and fixed arrays, direct and indirect calls,
variadics and `va_list` forwarding, mutable local/global/static storage,
initializers, arithmetic and casts, lvalues, indexing/member access,
conditionals, generic selection, compound literals, GNU statement expressions,
switch/fallthrough, loops, break/continue, goto/labels, and C linkage.
Unsupported typed-AST forms fail during lowering rather than falling back to
native C code generation.

This is not a conforming general-purpose C implementation. Bitfields, VLAs,
atomics, complex numbers, TLS, arbitrary irreducible goto graphs, and all
packed/over-aligned layouts are not complete.

## Validation

```sh
coil test --suite c
python3 scripts/c-multi-unit.py --compiler "$(command -v coil)"
python3 scripts/c-doom.py --compiler "$(command -v coil)"
```

The multi-unit gate checks positive linkage, incompatible declarations,
recursive record-layout incompatibility, and cJSON as two real translation
units. The Doom gate pins Doom Generic revision
`fc601639494e089702a1ada082eb51aaafc03722`, builds its 81 translation units,
runs exactly 1,000 frames with the pinned shareware WAD, and requires framebuffer
hash `734a03fe31906bc3`.
