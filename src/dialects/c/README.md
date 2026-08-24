# C frontends

Two of them share this directory. Both turn C into ordinary Coil, which Coil's
own backend then compiles; they differ in who reads the C.

The **native frontend** reads it itself. `cc.coil` lexes, preprocesses, parses,
type-checks, and lowers C11 with nothing but Coil code — no Clang, no JSON, no
external tool of any kind between the source text and the emitted Coil. It is
ported from [chibicc](https://github.com/rui314/chibicc) by Rui Ueyama; see
[ATTRIBUTION.md](ATTRIBUTION.md).

The **Clang-fed frontend** is the older one. Clang preprocesses and type-checks
each translation unit and dumps a typed JSON AST, which `ast.coil`, `build.coil`,
and `lower.coil` link and lower. Clang never emits IR, assembly, or objects
there either, but it does all the reading.

Both build the same pinned Doom Generic to the same framebuffer hash.

## The native frontend

```sh
coil run src/dialects/c/cc.coil -- -o out.coil a.c b.c \
  -include src/dialects/c/target/darwin-arm64.h \
  -include src/dialects/c/target/builtins.h \
  -I"$(xcrun --show-sdk-path)/usr/include" \
  -I"$(clang -print-resource-dir)/include" \
  -DNAME=value
coil build out.coil -O2 -o program
```

| module | what it does |
| --- | --- |
| `lex.coil` | tokens, keeping each one's original spelling so `#` can restate it |
| `pp.coil` | the preprocessor: macros, conditionals, `#include`, `_Pragma`, `__has_include` |
| `ctype.coil` | C's type system and record layout, bitfields and `packed` included |
| `node.coil` | the typed AST |
| `parse.coil` | the parser and the semantics: conversions, initialisers, constant expressions |
| `emit.coil` | lowering to Coil |
| `cc.coil` | the driver |
| `target/` | the target's predefined macros, and the builtins the system headers expect |

### Whole-program, one module

Every translation unit is preprocessed and parsed on its own — a macro defined in
one file means nothing in the next — and then all of them are lowered together
into a single Coil module. A call in one file reaches a definition in another
without a linker of our own, and a `static` name carries its unit's tag so two
files may each have their own `static int count`.

### How C constructs are represented

A record becomes a blob whose size and alignment are C's own: an array whose
element type carries the required alignment, with members reached by byte offset.
Handing records to Coil's struct layout instead would mean two independent sets
of layout rules had to agree, and they need not. It is also what makes bitfields
and `__attribute__((packed))` expressible at all.

Every expression has two forms, its value and its address. Assignment, `&`, and
member access all fall out of that rather than being special-cased, and an
update — `x op= y`, `x++` — computes its target's address once, so `*p++ += 1`
steps the pointer once.

A function containing a label is lowered through a control-flow graph and a
dispatch loop, because no arrangement of Coil's structured forms expresses a
`goto` that leaves a loop, enters one, or jumps backwards past a declaration.
Every other function keeps the structured lowering, which reads better and gives
the optimiser more.

A variadic function of the program's own takes a pointer to an argument area the
caller fills, laid out the way this target lays variadic arguments out on the
stack — one eight-byte slot each — so a `va_list` taken from it can be handed
straight to the C library's `vfprintf`. Calls to the C library's own variadic
functions use Coil's native `...` and the platform convention.

### What is not implemented

`_Float16` and `__int128` exist so that a system header declaring one lays out
correctly; arithmetic on either is reported rather than narrowed. Statement
expressions, generic selection, compound literals, VLAs, atomics, complex
numbers, thread-local storage, and inline assembly are not implemented. Each
reports where it appeared instead of quietly producing something else.

## The Clang-fed frontend

```sh
python3 scripts/c-build.py --compiler "$(command -v coil)" tests/c/fib.c -O0 -o /tmp/fib
python3 scripts/c-build.py --compiler "$(command -v coil)" \
  src/main.c src/render.c -O0 -o /tmp/game \
  --cflag=-Iinclude --cflag=-DFEATURE=1 --link-flag=-lm
```

`scripts/c-build.py` is a bootstrap harness with no frontend logic in it. Clang
is invoked by argv:

```text
clang -std=gnu11 -fsyntax-only -Wno-everything \
      <C flags> -Xclang -ast-dump=json <translation-unit.c>
```

Each source is preprocessed, type-checked, indexed, and lowered as a separate
translation unit; there is no source concatenation. The linker index validates
external declarations, tentative and initialised definitions, recursive record
layouts, unit-local `static` identities, constructors and destructors, and
function reachability before lowering. Bitfields, VLAs, atomics, complex numbers,
TLS, arbitrary irreducible goto graphs, and packed or over-aligned layouts are
not complete there.

## Validation

```sh
coil test --suite c                                              # unit tests
python3 scripts/c-native.py --compiler "$(command -v coil)"      # differential vs clang
python3 scripts/c-doom-native.py --compiler "$(command -v coil)" # Doom, native frontend
python3 scripts/c-multi-unit.py --compiler "$(command -v coil)"  # linkage, Clang path
python3 scripts/c-doom.py --compiler "$(command -v coil)"        # Doom, Clang path
```

`scripts/c-native.py` compiles every case in `tests/c/native/` twice — once with
Clang, once with the native frontend — runs both, and requires the exit status
and output to agree. Clang is the oracle there and nothing else; it is not part
of the build being tested.

Both Doom gates pin Doom Generic revision
`fc601639494e089702a1ada082eb51aaafc03722`, build its 81 translation units, run
exactly 1,000 frames against the pinned shareware WAD, and require framebuffer
hash `734a03fe31906bc3`.

`python3 scripts/c-doom-native.py --play` builds the windowed game instead:
84 translation units including a Cocoa backend and SDL2 sound.
