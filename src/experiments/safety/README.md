# Safety dialect

The comprehensive implementation checklist and coverage matrix lives in
[`SAFETY.md`](SAFETY.md).

Importing `experiments.safety.safety` installs a whole-program metaprogram that
adds runtime bounds checks to every `primitive/index` whose base has the checked
type `(ptr (array T N))`, as well as slice and ArrayList accessors. It also
validates subslice ranges, nullness and alignment before pointer
loads, stores, field access, and indexing. Raw pointers receive pointer checks but
cannot receive bounds checks because their allocation length is not represented in
their type, so raw-pointer indexing is rejected unless explicitly wrapped in
`unsafe`.

Indirect calls reject statically null targets and validate dynamic targets before
dispatch. Pointer-returning functions are rejected when their result is visibly
derived from local stack storage.

The dialect also rewrites ordinary signed and unsigned arithmetic, division,
remainder, and shifts to checked operations across the standard 8/16/32/64-bit
integer types. It checks narrowing and signedness-changing casts as well.
The corresponding raw integer primitives are rewritten too. Arithmetic or
conversion involving Coil's nonstandard-width integers is rejected unless marked
`unsafe`, rather than being allowed to wrap through an unchecked compiler primitive.
`experiments.safety.arithmetic` provides explicit
checked, wrapping, and saturating i64 operations, plus checked negation,
absolute-value, exact-division, and exact-shift operations for every standard
integer width.
`experiments.safety.unsafe` contains searchable unchecked pointer and truncating-cast
escape hatches.

Raw aliasing operations, arbitrary LLVM IR, raw deallocation, zero-bit-pattern
construction, and target register/control primitives are compile errors outside an
explicit `unsafe` wrapper. Volatile and packed-bitfield memory operations receive the
same null/alignment validation as ordinary loads and stores. Dynamic values receive
constant-time data/vtable null and alignment validation before they cross a dynamic
parameter boundary or dispatch a method; compiler-created vtable provenance avoids
dynamic-loader lookup on the hot path.

`experiments.safety.sums` supplies trapping Option and Result unwrap operations.
`experiments.safety.ffi` validates nonnull, pointer-plus-length, allocation-size,
C-string sentinel, alignment, and non-overlap contracts at foreign boundaries.

```coil
(import "experiments.safety.safety" :use *)

(let [xs (primitive/alloc-stack (array i64 4))]
  (load (primitive/index xs i))) ; traps unless 0 <= i < 4
```

Run the example from this directory with `coil run`. For the complete Zig-like
development profile, combine the dialect with Coil's compiler checks:

```sh
coil run demo.coil --debug-checks --sanitize=undefined
```

`--debug-checks` enables the compiler's bounds, collection, allocator, and
stack-return checks. `--sanitize=undefined` catches integer overflow and invalid
divide/shift operations. `--debug-runtime` is the convenient checks + AddressSanitizer
profile when memory diagnostics are wanted too.

From the workspace root, `scripts/safety-check.sh FILE.coil` emits separate
undefined-behavior and AddressSanitizer-instrumented objects. ThreadSanitizer and the
Linux-only MemorySanitizer remain separate CI passes because sanitizer runtimes
cannot be combined in one artifact.

`scripts/safety-test.sh` runs the positive unit tests and verifies every negative
fixture traps with its intended diagnostic.
