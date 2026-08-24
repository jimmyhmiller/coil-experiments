# A `const` holding an aggregate silently loses fields

`(const NAME (load (Struct :a 1 :b 2)))` compiles, and reads back the wrong
value. No diagnostic. Fields narrower than eight bytes go missing; the last one
always does.

Measured on `coil` at `/Users/jimmyhmiller/.cargo/bin/coil`, macOS arm64.

## Reproducing

```lisp
(module agg)
(import "coil.primitive" :as primitive)

(defstruct S3 [(a i32) (b i32) (c i32)])
(const K (load (S3 :a 1 :b 2 :c 3)))

(defn main [] (-> i32)
  (let [cell (primitive/alloc-stack S3)]
    (set! cell K)
    (println "{d} {d} {d}"
             (primitive/cast i64 (load (primitive/index (primitive/cast (ptr i32) cell) 0)))
             (primitive/cast i64 (load (primitive/index (primitive/cast (ptr i32) cell) 1)))
             (primitive/cast i64 (load (primitive/index (primitive/cast (ptr i32) cell) 2)))))
  0)
```

```text
1 2 0        ← want 1 2 3
```

## The shape of it

| struct | fields | expected | actual |
| --- | --- | --- | --- |
| `[(a i32)]` | 1 | `1` | `0` |
| `[(a i32) (b i32)]` | 2 | `1 2` | `1 0` |
| `[(a i32) (b i32) (c i32)]` | 3 | `1 2 3` | `1 2 0` |
| `[(a i32) … (d i32)]` | 4 | `1 2 3 4` | `1 2 3 0` |
| `[(a i32) … (e i32)]` | 5 | `1 2 3 4 5` | `1 2 3 4 0` |
| `[(a u8) (b u8) (c u8)]` | 3 | `1 2 3` | `0 0 0` |
| `[(a i64)]` | 1 | `1` | `1` |
| `[(a i64) (b i64)]` | 2 | `1 2` | `1 2` |
| `[(a i64) (b i64) (c i64)]` | 3 | `1 2 3` | `1 2 3` |

With `i32` fields the last field is zero, whatever the count. With `u8` fields
every field is zero. With `i64` fields the value is correct, including values
that need the high half of the word (`4294967318` round-trips).

Constructing the same struct at run time is correct, so it is the `const`
materialisation and not the constructor or the field access:

```lisp
(let [(mut here) (load (Pt :x 3 :y 4))] …)   ; x=3 y=4
(let [(mut there) K-PT] …)                   ; x=3 y=0
```

## Why it matters here

The C frontend has a use for exactly this. A C program's initialised tables --
Doom's `states[]` and `mobjinfo[]` are 52 KB of them -- are bytes in the object
file when Clang compiles them, with `__text` of size zero: no code runs to build
them. The frontend cannot do that today, so it emits 36,171 stores that run
before `main`, which is 44% of the whole generated module.

`c"…"` does put exact bytes in the image, so the frontend can close that gap by
laying the tables out itself and emitting one byte literal per table -- verified,
the bytes land in `__const`. But that spells a table of structs as a run of hex
escapes. A `const` of aggregate type would let the same tables be written with
their values and field names visible, which is the difference between generated
code you can read and generated code you can only trust.

## What would fix it

Materialising every field of an aggregate `const`, whatever its width.

Failing that: rejecting the ones that cannot be materialised. A silent zero is
the worst of the three outcomes, and the guidance in the language notes -- that
comptime results must be materializable literals -- suggests this case is known
to be restricted. The restriction just is not enforced.
