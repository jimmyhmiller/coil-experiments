# A C compiler written in Coil

`cc.coil` lexes, preprocesses, parses, type-checks, and lowers C11 with nothing
but Coil code. No Clang, no JSON, no external tool of any kind stands between the
source text and the emitted Coil — the C11 frontend is the program in this
directory. It is ported from [chibicc](https://github.com/rui314/chibicc) by Rui
Ueyama; see [ATTRIBUTION.md](ATTRIBUTION.md).

The output is ordinary Coil, which Coil's own backend compiles.

```sh
coil run src/dialects/c/cc_main.coil -- -o out.coil a.c b.c \
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
| `cc.coil` | the reusable compiler pipeline used by readers and tools |
| `cc_main.coil` | the command-line entry point |
| `target/` | the target's predefined macros, and the builtins the system headers expect |

## Many translation units, one module

Every `.c` file is preprocessed and parsed on its own — a macro defined in one
file means nothing in the next, and a `struct` declared in one is a different
type object from the identically-named one next door. All of them are then
lowered together into a single Coil module, so a call in one file reaches a
definition in another without any linker of ours in between. See
[MULTI-UNIT.md](MULTI-UNIT.md) for what that costs, what it buys, and what the
commands and intermediate files actually look like.

The same frontend can be used directly as a project reader, so generated Coil
does not need to be stored on disk:

```toml
[manifest.providers]
c = "experiments.c.reader"

[readers]
".cmod" = "experiments.c.reader"

[modules]
"myapp.raylib" = "vendor/raylib.cmod"

[c.raylib]
sources = ["vendor/raylib/src/rcore.c", "vendor/raylib/src/rshapes.c"]
include-paths = ["vendor/raylib/src"]
defines = ["PLATFORM_DESKTOP_SDL", "GRAPHICS_API_OPENGL_33"]
prefixes = ["src/dialects/c/target/darwin-arm64.h"]
```

Import `"myapp.raylib"` like any other module. The `.cmod` file is the module
anchor; its basename selects `[c.raylib]`. The reader preprocesses every source
as an independent C translation unit and returns one in-memory Coil module.

## How C constructs are represented

A complete, nameable C record becomes an explicit-layout Coil `defstruct`, with
the C frontend supplying every field offset plus the record's size and alignment.
This gives callers ordinary constructors such as `(Color :r 17 :g 34 :b 51
:a 255)` while preserving C layout. Opaque/incomplete records remain raw storage;
bitfields and anonymous members use byte-offset access where a Coil field cannot
express the C operation.

Every expression has two forms, its value and its address. Assignment, `&`, and
member access all fall out of that rather than being special-cased, and an
update — `x op= y`, `x++` — computes its target's address once, so `*p++ += 1`
steps the pointer once.

An object with static storage is defined to hold its value rather than being
written at start-up. Every leaf of an initialiser that folds to a number is laid
into the object's image and the object is emitted holding it, so the bytes are in
the binary and the loader maps them, the same as a C compiler. Only the leaves
whose value is an address the linker decides — a string, another object, a
function — are left as stores that run before `main`.

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

`__attribute__((constructor))` and `((destructor))` run around `main`:
constructors after the static initialisers, destructors through `atexit`, so that
they still run when the program calls `exit`.

## Records across a foreign call boundary

The emitted explicit-layout structs preserve the layout and field types needed
by Coil's native ABI classifier. Struct arguments and returns work both between
translated functions and for foreign calls such as Raylib's `Color` and
`Vector2` APIs; `tests/c/native/structs.c` checks translated calls against Clang
and the Raylib reader demo exercises the external boundary.

`src/apps/doom/cocoa.c` is the only place in this repo that would do it -- a
`CGRect` to `objc_msgSend` -- and it sends the four doubles as four arguments
instead, which this target puts in exactly the same registers.

## What is not implemented

`_Float16` and `__int128` exist so that a system header declaring one lays out
correctly; arithmetic on either is reported rather than narrowed. Generic
selection, VLAs, complex numbers, thread-local storage, and general inline
assembly are not implemented. C11 `_Atomic(T)` plus the exchange/load/store
builtins, GCC `__sync_*` integer atomics, empty GNU asm compiler barriers, and
the AArch64 `yield` hint are supported. Implicit function declarations are
rejected, as C99 and Clang reject them. Each unsupported construct reports where
it appeared instead of quietly producing something else.

## Validation

```sh
coil test --suite c                                              # unit tests
python3 scripts/c-native.py --compiler "$(command -v coil)"      # differential vs clang
python3 scripts/c-doom-native.py --compiler "$(command -v coil)" # Doom
```

`scripts/c-native.py` compiles every case in `tests/c/native/` and every project
in its `PROJECTS` list twice — once with Clang, once with this frontend — runs
both, and requires the exit status and output to agree. Clang is the oracle there
and nothing else; it takes no part in the build being tested.

The Doom gate pins Doom Generic revision
`fc601639494e089702a1ada082eb51aaafc03722`, builds its 81 translation units, runs
exactly 1,000 frames against the pinned shareware WAD, and requires framebuffer
hash `734a03fe31906bc3` — the same hash a Clang-built Doom produces.

`python3 scripts/c-doom-native.py --play` builds the windowed game instead: 84
translation units including a Cocoa backend and SDL2 sound.
