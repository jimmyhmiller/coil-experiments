# Coil cannot say what is in a static

There is no way to give a static its contents. `primitive/alloc-static` allocates
zeroed storage and takes no initial value, and nothing else produces initialised,
writable, aligned storage. The only initialised data Coil can put in a binary is
a string literal, which is read-only and byte-aligned.

Every route was tried; all three are below. Measured on `coil` at
`/Users/jimmyhmiller/.cargo/bin/coil`, macOS arm64.

## What this costs

A C program's initialised tables are bytes in the object file. Doom's `info.c`
compiled by Clang:

```text
Section (__DATA, __data): 52396      52 KB of table
Section (__TEXT, __text): 0          no code at all
```

Nothing runs to build them; the loader maps them. The C frontend in
`src/dialects/c/` cannot do that, so it emits **36,171 stores** that run before
`main` — **44% of the entire generated module** — to reproduce at start-up what a
C compiler writes down once.

Those tables are not `const`, and that matters: Doom's dehacked support patches
`states[]` and `mobjinfo[]` at run time, so whatever holds them has to be
writable.

## Route 1 — `alloc-static` has no initialiser

```lisp
(defn c_g_states [] (-> (ptr (array i64 15))) (primitive/alloc-static (array i64 15)))
```

Zeroed, and there is no second argument. This is the shape the frontend uses,
and the reason for the 36,171 stores.

## Route 2 — a string literal is read-only and byte-aligned

`c"…"` does put exact bytes in the image — verified, they land in `__const`, and
a four-`i32` table read back correctly. But it is not storage:

```lisp
(defn blob [] (-> (ptr (array i32 3)))
  (primitive/cast (ptr (array i32 3)) c"\xb;\0\0\0\x16;\0\0\0\x21;\0\0\0"))

(let [p (primitive/cast (ptr i32) (blob))]
  (set! (primitive/index p 1) (primitive/cast i32 999)))
```

```text
-O0 : before : 11 22 33
      address: 4298968859
      [exit 138 — SIGBUS]

-O3 : before : 11 22 33
      after  : 11 22 33      the write is dropped, the reads fold, no crash
```

Two separate problems:

- **Read-only.** A table with any address in it cannot be baked, because an
  address is not known until link time — that is what C solves with relocations
  (`ARM64_RELOC_UNSIGNED _A_Explode`, 586 of them in `info.c`). Patching them in
  at start-up is the obvious substitute, and it bus-errors.
- **Byte-aligned.** `4298968859` is odd. A table of `i64` laid out there is
  misaligned.

The `-O3` behaviour is worth a look on its own: the same invalid write is
silently discarded rather than trapping, and the reads are folded from the
literal, so the program prints stale values instead of failing.

## Route 3 — a `const` of aggregate type silently drops fields

```lisp
(defstruct S3 [(a i32) (b i32) (c i32)])
(const K (load (S3 :a 1 :b 2 :c 3)))
```

reads back `1 2 0`. No diagnostic.

| struct | expected | actual |
| --- | --- | --- |
| `[(a i32)]` | `1` | `0` |
| `[(a i32) (b i32)]` | `1 2` | `1 0` |
| `[(a i32) (b i32) (c i32)]` | `1 2 3` | `1 2 0` |
| `[(a i32) … (e i32)]` | `1 2 3 4 5` | `1 2 3 4 0` |
| `[(a u8) (b u8) (c u8)]` | `1 2 3` | `0 0 0` |
| `[(a i64)]` | `1` | `1` |
| `[(a i64) (b i64) (c i64)]` | `1 2 3` | `1 2 3` |

With `i32` fields the last field is zero at any count; with `u8` fields every
field is; with `i64` fields it is correct, including values needing the high half
of the word. Building the same struct at run time is correct, so it is the
`const` materialisation.

A silent zero is the worst of the available outcomes. The language notes already
say comptime results must be materializable literals — the restriction exists,
it just is not enforced.

## And a macro cannot work around it

A metaprogram can compute the bytes, but it cannot hand back a literal: there is
no constructor for a string `Code` node. `datum->syntax` produces a *symbol*, so
a computed byte string comes out as an identifier —

```text
error: in 'bake.table': unbound variable '      !   '
```

— and `code-read`, which is documented as being for `:phase read` metaprograms
that delegate to the built-in reader, rejects a computed string:

```text
error: code-read: expects string Code and reader-config Code
```

So the readable form and the baked form cannot be the same form. A macro can make
the source say what the C said, but it has to expand to stores.

## What would fix it

An initial value on a static:

```lisp
(primitive/alloc-static (array i64 15) <initial>)
```

writable, aligned to the type, and laid into the binary. That is the whole ask.
It would delete 44% of the generated C module, and it is the same primitive any
program with a table of constants wants.

Failing that, in rough order of usefulness:

1. **Fix route 3** so a `const` can hold an aggregate — then a static could at
   least be initialised by one copy rather than field by field. Or reject it, so
   it stops being silently wrong.
2. **Make a string literal's alignment declarable**, and say what writing to one
   does — trap at every optimisation level, or be allowed.
3. **A constructor for a string `Code` node**, so a metaprogram can produce
   literal data.
