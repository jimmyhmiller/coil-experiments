# How several `.c` files become one program

There is no linker here, and no object files. Every translation unit is read on
its own, and then all of them are lowered together into **one** Coil module,
which Coil's backend compiles into one object and links once against libc.

This page is the concrete version of that: the commands, the file that comes out,
and what the names in it mean.

## The example

`tests/c/multi-unit/` is two files that share a header and nothing else. It is
deliberately awkward:

- `alpha.c` and `beta.c` each define a **different** `static int counter`.
- `int shared;` appears at file scope in **both** — one object, two tentative
  definitions.
- `int initialized = 7;` is defined in `alpha.c` and declared `extern` in the
  header.
- `beta.c` calls `from_alpha`, `alpha.c` calls `from_beta`: the call graph
  crosses the file boundary in both directions.
- `apply` takes a function pointer from one file and calls a `static` function
  of the other.
- `report` is variadic, defined in `alpha.c`, called from `beta.c`.
- each file has an `__attribute__((constructor))` and a `((destructor))`.

## Compiling it

One command. Every `.c` on the line, one `-o`:

```sh
coil run src/dialects/c/cc.coil -- \
  -o /tmp/mu.coil \
  tests/c/multi-unit/alpha.c tests/c/multi-unit/beta.c \
  -Itests/c/multi-unit \
  -D_FORTIFY_SOURCE=0 \
  -include src/dialects/c/target/darwin-arm64.h \
  -include src/dialects/c/target/builtins.h \
  -I"$(clang -print-resource-dir)/include" \
  -I"$(xcrun --show-sdk-path)/usr/include"

coil build /tmp/mu.coil -O0 -o /tmp/mu
/tmp/mu
```

```text
alpha+
beta+
linked-varargs=1
main=1
beta-
alpha-
```

`-I`, `-D`, and `-include` mean what they mean to any C compiler. `-include`
is how the target's predefined macros reach the preprocessor: they are a header
of ordinary `#define`s in `target/`, not a table inside the driver.

There is exactly one output file, `/tmp/mu.coil`: 132 lines of Coil for these
two sources. It is meant to be read.

## What is in the output

```lisp
(module c_program)
(import "coil.primitive" :as primitive)
(import "coil.alloc" :as alloc)
(import "coil.control" :as control)
(import "coil.slice" :as slice)
(extern atexit :cc c [(fnptr c [] i64)] (-> i32))
(extern printf :cc c [(ptr i8) ...] (-> i32))
(extern __swbuf :cc c [i32 (ptr i8)] (-> i32))
(defn c_g_counter_alpha [] (-> (ptr i32)) (primitive/alloc-static i32))
(defn c_g_shared [] (-> (ptr i32)) (primitive/alloc-static i32))
(defn c_g_initialized [] (-> (ptr i32)) (primitive/alloc-static i32))
...
(defn c_g_counter_beta [] (-> (ptr i32)) (primitive/alloc-static i32))
```

Four kinds of thing appear, in this order:

1. **`extern` declarations** for the C library functions the program actually
   calls. Only the ones it calls: a system header declares hundreds, and
   declaring all of them would drag in types this compiler has no arithmetic
   for. Anything reachable from a function body or a static initialiser is
   counted as called.
2. **A zero-argument accessor per global**, returning its address. That is how a
   C object with static storage is spelled: `(primitive/alloc-static T)` gives
   one cell per call site, and the call site is inside the accessor, so every
   reader of `c_g_shared` gets the same cell. A global that is declared but
   never defined anywhere in the program gets an accessor over a real external
   symbol instead.
3. **The function bodies**, one `defn` each.
4. **`c_init_statics` and `main`**, which are described below.

## How the names are kept apart

Both files define `static int counter`. Both are in the same module. They are
different objects, and they must stay different.

The parser gives each unit a tag — the file's basename — and appends it to every
name that belongs to one file only:

| C declaration | in the AST | in the emitted Coil |
| --- | --- | --- |
| `static int counter;` in `alpha.c` | `counter$alpha` | `c_g_counter_alpha` |
| `static int counter;` in `beta.c` | `counter$beta` | `c_g_counter_beta` |
| `int shared;` (either file) | `shared` | `c_g_shared` |
| `static int increment(int)` in `alpha.c` | `increment$alpha` | `c_fn_increment_alpha` |
| `int from_alpha(struct Pair *)` | `from_alpha` | `c_fn_from_alpha` |
| a string literal, twelfth in `alpha.c` | `.Lstr.12$alpha` | `c_g__Lstr_12_alpha` |

The name the source used stays bound in the file's own scope, so `counter` inside
`alpha.c` finds `counter$alpha` and nothing else. The `$` is only in the AST;
the emitter maps every character outside `[A-Za-z0-9_]` to `_` when it writes the
Coil identifier.

Static locals get the same treatment plus a serial, because two functions in one
file may each have a `static int n`.

This is also why string literals carry a tag. They did not at first, and the
twelfth literal of one file quietly became the twelfth literal of another —
`fprintf(stderr, "\n\n")` printed somebody else's message.

## How the two files find each other

They do not, in the sense a linker means. Nothing resolves anything.

`beta.c` calls `from_alpha`. The parser sees the header's declaration and makes
an object named `from_alpha` with no body. `alpha.c` defines a function with the
same name. Both objects end up in one list, and before emitting anything the
lowerer walks that list once and records which names have a definition somewhere.
A call then emits `(c_fn_from_alpha ...)` if the name is defined in the program,
and `(from_alpha ...)` — a call to an external symbol — if it is not. That single
pass is the whole of "linking".

The same pass decides three other things:

- **Which declaration describes the storage.** `extern char *sprnames[];` in a
  header and `char *sprnames[NUMSPRITES] = {...}` in one file are two objects
  with one name and two sizes. The one with the larger type wins, so the array
  gets its real length rather than the header's empty brackets.
- **Whether a global is ours or somebody else's.** `int shared;` in both files
  is defined, so one accessor over `alloc-static` is emitted and both files use
  it. `extern FILE *__stderrp;` is never defined, so it becomes an external
  symbol reference. Getting this wrong means silently allocating a private copy
  of `stderr`.
- **What is used.** A declaration nothing refers to is dropped rather than
  emitted as an `extern`.

## What is checked, and what is not

There is no separate ABI check across units, because there is nothing to check
across: the whole program is one module and Coil's own typechecker sees every
call and every definition at once. A disagreement is caught there.

```sh
printf 'int mismatch(int x) { return x; }\n'                       > /tmp/l.c
printf 'double mismatch(double);\nint main(void){return (int)mismatch(1.5);}\n' > /tmp/r.c
# ... cc.coil -o /tmp/bad.coil /tmp/l.c /tmp/r.c ...
coil build /tmp/bad.coil -O0 -o /tmp/bad
```

```text
error: in 'c_program.c_fn_main': argument 1 to 'c_program.c_fn_mismatch'
       has type f64 but expected i32
```

The frontend accepts both files — each is valid on its own — and the mismatch
surfaces when the module is compiled. The message names the generated function
rather than the C declaration, which is the honest cost of not having a linker
index: the diagnostic is one level down from the source.

Types themselves are never shared between units. `struct Pair` in `alpha.c` and
`struct Pair` in `beta.c` are two type objects that happen to agree. Nothing
compares them, and nothing needs to: a record is lowered as a blob of C's own
size and alignment, and a pointer to any record is `(ptr i8)`, so two units that
lay the same header out the same way produce the same code either way. A header
that says `typedef struct _MEMFILE MEMFILE;` gives one file a complete type and
every other file an opaque one — that is why the pointer type is deliberately
uninformative.

## Start-up and shutdown

Everything with static storage is initialised in one function, in source order,
unit by unit:

```lisp
(defn c_init_statics [] (-> i64)
  (do
    (do ...alpha.c's initialisers...)
    (do ...beta.c's initialisers...)
    (atexit (primitive/fnptr-of c_fn_alpha_stop_alpha))
    (atexit (primitive/fnptr-of c_fn_beta_stop_beta))
    (c_fn_alpha_start_alpha)
    (c_fn_beta_start_beta)
    0))

(defn main [(argc i32) (argv (ptr (ptr i8)))] (-> i32)
  (do (c_init_statics) (primitive/cast i32 (c_fn_main argc argv))))
```

Most of what a C program initialises never reaches that function. An object with
static storage is *defined* to hold its value — the bytes are in the binary, and
the loader maps them — exactly as a C compiler writes them down. What is left in
`c_init_statics` is the initialisers no constant can spell: the ones whose value
is an address the linker decides. Doom's 36,171 start-up stores come to 1,305
this way, and `c_init_statics` falls from 44% of the generated module to 4.5%.

C's static initialisers are not restricted to constants here — `int *p = &x;`
works — because whatever is left is an ordinary store that runs before anything
else. Then the
`constructor` functions run, in priority order and then declaration order, and
the `destructor` functions are handed to `atexit`, which runs its list backwards:
registering them forwards is what makes them run in reverse, `beta-` before
`alpha-`.

The entry point takes `argc` and `argv` only if the program's `main` declared
them.

## The costs

- **Compilation is whole-program.** Changing one file recompiles everything.
  There is no separate compilation and no incremental build.
- **One name space.** Every unit's declarations live in one Coil module, which
  is why the tagging above has to be right rather than merely convenient.
- **Diagnostics for cross-unit disagreements come from the backend**, in terms of
  generated names.
- **The output is one large file.** Doom's 81 units are about 17 MB of Coil.
  `coil build -O0` takes a couple of minutes on it.

What it buys is that there is nothing between the C and the machine code except
Coil: no object format, no relocation, no symbol table of ours, and no second
implementation of C's linkage rules to keep in step with the first.
