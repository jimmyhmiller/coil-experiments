# Coil has no way to write a byte ≥ 0x80 into a string literal

`(slice u8)` is a byte string, but the literal syntax that produces one can only
express code points. There is no escape that means "this byte", and no other way
to get initialised byte storage. Anything that has to put arbitrary bytes in a
program — the C frontend is the case at hand, but so is any binary blob — needs
a second mechanism that writes them at run time.

Measured on `coil` at `/Users/jimmyhmiller/.cargo/bin/coil`, macOS arm64.

## The escape set

From the compiler's own diagnostic:

```text
error: unknown string escape (known: \n \t \r \0 \" \\ \xHEX;)
```

Six fixed escapes and `\xHEX;`.

## `\xHEX;` is a code point, not a byte

```lisp
(dump "\x7f;")   ; len=1  bytes=127
(dump "\x80;")   ; len=2  bytes=194 128
(dump "\x81;")   ; len=2  bytes=194 129
(dump "\xfe;")   ; len=2  bytes=195 190
(dump "\xff;")   ; len=2  bytes=195 191
```

The boundary is exactly 0x80. At and above it the escape UTF-8-encodes, so a
literal cannot contain a lone high byte at all. `"\x80;"` is two bytes and there
is no spelling that gives one.

The rest of the syntax is fine, for the record — these all behave as bytes:

```lisp
(dump "WIMINUS\0")  ; len=8  bytes=87 73 77 73 78 85 83 0
(dump "%d{}")       ; len=4  bytes=37 100 123 125
(dump "a\"b\\c")    ; len=5  bytes=97 34 98 92 99
(dump "a\09b")      ; len=4  bytes=97 0 57 98     -- \0 is a fixed escape, not octal
```

`\0` in particular works, which matters: NUL termination is not the problem here.

## There is no other route to initialised byte storage

`primitive/alloc-static` gives zeroed storage and takes no initialiser:

```lisp
(defn array-of-bytes [] (-> (ptr (array u8 3)))
  (primitive/alloc-static (array u8 3)))
;; every element reads 0; there is no way to say otherwise
```

There is no byte-string literal (`b"…"`), no array literal, and nothing in
`coil.slice` that builds static data. A string literal plus `slice-data` is the
only way to get bytes into the binary, and it inherits the limitation above.

## What it costs the C frontend

A C string literal is an arbitrary byte string. `src/dialects/c/emit.coil`
therefore carries two paths:

1. **All bytes < 0x80** — the literal goes out as static data, one accessor:

   ```lisp
   (defn c_g__Lstr_743_wi_stuff [] (-> (ptr (array i8 7)))
     (primitive/cast (ptr (array i8 7)) (slice/slice-data [u8] "WIPCNT\0")))
   ```

2. **Any byte ≥ 0x80** — the literal cannot be written, so it becomes a zeroed
   `alloc-static` array plus one store per byte in the program's start-up
   function:

   ```lisp
   (primitive/store! (primitive/index (primitive/cast (ptr u8) (c_g__Lstr_9_x)) 0)
                     (primitive/cast u8 195))
   ...
   ```

   That is `ascii-string?`, `emit-string-fill!`, and the branch in `emit-global!`
   — code that exists only because of this, and that turns a constant into
   start-up work.

Doom does not hit path 2: 192 files, **3,305 string literals, 0 containing a byte
≥ 0x80** — and 1,480 distinct literals in the emitted module, all static data. So
this is not blocking anything today. It is a correctness cliff that the frontend
has to carry code for, and any C program with a non-UTF-8 byte in a literal —
Latin-1 text, a lookup table written as a string, an embedded binary constant —
falls off it.

## What would fix it

A raw-byte escape. Something that means "emit this one byte" rather than "emit
this code point", so that

```lisp
"\xff;"     ; today: 2 bytes, 195 191
```

has a counterpart that is one byte, 255. The spelling is yours — a different
letter (`\bFF;`), a different terminator, a prefix on the literal (`b"…"`) — the
requirement is only that every value 0–255 be expressible as itself and that the
result still be a `(slice u8)` whose length is the number of bytes written.

With that, path 2 above goes away entirely and every C string literal in any
program becomes static data.

A byte-string literal form would do just as well and would additionally cover
the general "I want this blob in my binary" case, which `alloc-static` cannot
express at all.

## Smaller, not blocking

C has `\a \b \f \v \e`; Coil has none of them. They are all below 0x80 so
`\xHEX;` covers them, at the cost of the emitted module reading
`"\x1b;[2J"` rather than `"\e[2J"`. Worth having, but nothing depends on it.
