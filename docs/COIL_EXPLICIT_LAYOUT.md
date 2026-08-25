# Two gaps in `:layout explicit` and `:layout bits`

Found while working out whether the C frontend can give its records real
`defstruct`s instead of blobs. Everything else works: `:at` offsets,
`sizeof`/`offsetof`/`static-assert`, reaching a struct through a `(ptr i8)` and
casting back, arrays of them, and run-time `load`/`set!` of every field.

Measured on `coil` at `/Users/jimmyhmiller/.cargo/bin/coil`, macOS arm64.

## 1. `alloc-static` writes only the first field of a `:layout explicit` struct

```lisp
(defstruct W :layout explicit :size 24 :align 8
  [(a :i64 :at 0) (b :i64 :at 8) (c :i64 :at 16)])
(defstruct C [(a :i64) (b :i64) (c :i64)])          ; the same thing, :layout c

(defn w [] (-> (ptr W)) (primitive/alloc-static W (W :a 11 :b 22 :c 33)))
(defn c [] (-> (ptr C)) (primitive/alloc-static C (C :a 11 :b 22 :c 33)))
```

```text
explicit W      a=11 b=0 c=0        <-- wrong
default  C      a=11 b=22 c=33
packed   K      a=1  b=2            <-- :layout packed is fine
array of W [1]  a=4  b=0 c=0        <-- same, per element
```

Every field after the first comes back zero. It is not an offset mismatch: `W`'s
stated offsets are the natural ones here, `sizeof` and `offsetof` report them
correctly, and writing the same fields at run time with `set!` works. Only the
initialiser drops them.

`:layout c` and `:layout packed` both bake correctly, so this is specific to the
byte-blob realization `:explicit` lowers to.

## 2. A `:layout bits` field cannot be signed

```lisp
(defstruct Bits :layout bits :backing :u32
  [(a :bits 3) (b :bits 5) (c :bits 9)])

(primitive/bit-set! p c (primitive/cast :i9 -100))
;; error: set! into bitfield 'c' has type i9 but expected u9
```

C has signed bitfields — `struct { int c : 9; }` holds -256..255, and reading it
sign-extends. There is no way to say that: every `:bits` field is unsigned, so a
frontend has to sign-extend by hand on every read and mask on every write, which
is what it was already doing with the blob.

## Why this matters here

`src/dialects/c/emit.coil` lowers a C record to a blob — an array of the widest
unit its alignment allows — and reaches members by byte offset. With `:layout
explicit :at` it could emit the offsets `ctype.coil` computed and get named
fields: `(load (.flags ld))` instead of `(load (c_at i32 ld 16))`, across roughly
10,600 member accesses in Doom.

Neither gap blocks that, because the frontend can keep blob *storage* (which
bakes correctly) and use the struct purely as a view for access. But (1) closes
off the simpler design where the struct is also the storage, and (2) means
signed bitfields keep their hand-written shifting either way.
