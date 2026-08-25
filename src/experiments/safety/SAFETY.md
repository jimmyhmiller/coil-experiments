# Zig-style safety for Coil

This document tracks safety-checked illegal behavior in the language and build.
Its scope is deliberately the same kind of safety Zig enables in Debug and
ReleaseSafe modes: prevent a typed operation from silently producing undefined or
illegal behavior.

It does **not** cover application protocol state, resource lifecycles, business
rules, or ownership/borrowing.

Status:

- **covered** — implemented and regression-tested;
- **not applicable** — Coil's type system does not expose the illegal operation.

## Safety-checked illegal behavior

| Illegal behavior | Coil implementation | Status |
|---|---|---|
| Index out of bounds | Safety transform checks fixed arrays, slices, and ArrayList accessors | **covered** |
| Invalid subslice range | Safety transform validates both bounds and `lo <= hi` | **covered** |
| Negative signed-to-unsigned cast | Safety transform validates standard integer widths | **covered** |
| Integer cast truncates data | Safety transform validates 8/16/32/64-bit integer casts | **covered** |
| Unsigned-to-signed value out of range | Safety transform validates destination range | **covered** |
| Float-to-integer value out of range | Safety transform checks f32/f64, rejecting NaN, infinity, and values outside the destination interval | **covered** |
| Signed addition overflow | Safety transform rewrites ordinary `+` for all standard signed widths | **covered** |
| Signed subtraction overflow | Safety transform rewrites ordinary `-` for all standard signed widths | **covered** |
| Signed multiplication overflow | Safety transform rewrites ordinary `*` for all standard signed widths | **covered** |
| Unsigned addition/subtraction/multiplication overflow | Safety transform rewrites ordinary arithmetic for all standard unsigned widths | **covered** |
| Signed negation/absolute-value overflow | Subtraction-form negation and checked absolute-value APIs cover i8/i16/i32/i64 | **covered** |
| Division by zero | Safety transform rewrites ordinary `/` for all standard widths | **covered** |
| Remainder by zero | Safety transform rewrites ordinary `%` for all standard widths | **covered** |
| Signed minimum divided by `-1` | Checked by the ordinary division rewrite | **covered** |
| Exact division has a remainder | `exact-div-*` APIs for all standard integer widths | **covered** |
| Negative or oversized shift amount | Safety transform rewrites ordinary shifts for all standard widths | **covered** |
| Exact left/right shift discards bits | `checked-shl-*` and `checked-shr-*` for all standard integer widths | **covered** |
| Reached unreachable code | Dialect form `(unreachable)` traps | **covered** |
| Attempt to unwrap null/None | `expect-some` traps | **covered** |
| Attempt to unwrap an error as success | `expect-ok` traps; `expect-err` provides the inverse check | **covered** |
| Invalid enum/error code or cast | Coil sums cannot be constructed through integer casts | **not applicable** for ordinary typed code |
| Wrong tagged-union field access | Payloads are only available in exhaustive `match` arms | **covered** |
| Non-exhaustive tagged-union match | Compiler rejection with compile-fail regression | **covered** |
| Incorrect pointer alignment | Safety transform checks alignment before load/store/field/index | **covered** |
| Null pointer dereference | Safety transform checks load/store/field/index | **covered** |
| Use a null pointer | Null sentinels may be constructed/compared; dereference and indirect call reject null | **covered** |
| Invalid indirect call | Safety transform rejects constant null targets and validates dynamic targets against loaded images | **covered** |
| Invalid dynamic dispatch object/vtable | Compiler construction guarantees vtable provenance; the safety transform validates nonnull data plus nonnull/aligned vtable pointers at `(dyn Trait)` boundaries | **covered** |
| Returning a pointer to a stack local | Safety transform conservatively rejects stack allocation anywhere in a pointer-returning result; `unsafe` is the explicit override | **covered** |
| Falling off a non-void function | Compiler return-type checking with compile-fail regression | **covered** |
| Raw integer primitives bypass checked arithmetic | `iadd`/`isub`/`imul`/signed and unsigned division, remainder, and shifts are rewritten exactly like ordinary operators | **covered** |
| Unchecked nonstandard-width integer arithmetic or conversion | Rejected outside explicit `unsafe`; no unchecked fallback is permitted | **covered** |
| Volatile or packed-bitfield access through null/misaligned pointers | Volatile load/store and bitfield get/set receive the same pointer checks as ordinary memory access | **covered** |
| Lengthless raw-pointer indexing | Rejected outside explicit `unsafe`; a length-bearing array pointer, slice, or collection is required for checked indexing | **covered** |
| Unverifiable aliasing, arbitrary LLVM, raw free, or target-control operation | Rejected outside explicit `unsafe` | **covered** |
| Use of a zero-initialized pointer/dynamic value | Construction is allowed; dereference, indirect call, and dynamic dispatch validate before use | **covered** |

## Explicit arithmetic policies

Ordinary signed and unsigned arithmetic is rewritten to checked operations by the
safety transform. Code that intends a different policy must say so explicitly:

- `checked-add-i64`, `checked-sub-i64`, `checked-mul-i64`, checked negation and absolute value;
- `wrapping-add-i64`, `wrapping-sub-i64`, `wrapping-mul-i64`;
- `saturating-add-i64`, `saturating-sub-i64`;
- `exact-div-*`, `checked-shl-*`, and `checked-shr-*` for every standard integer width.

The library names alternative policies explicitly. The compiler's undefined-
behavior profile remains an independent backstop for code outside the transform.

## Pointer and range contracts

The safety transform handles operations whose checked type contains enough
information:

- `(ptr (array T N))` indexing receives a bounds check;
- slice get/set and subslicing receive unconditional index/range checks;
- ArrayList get/set/element-pointer access receives an unconditional length check;
- pointer loads, stores, fields, and indexing receive null/alignment checks;
- volatile loads/stores and packed-bitfield get/set receive null/alignment checks;
- constant null dereferences and constant fixed-array bounds failures are compile
  errors;
- raw pointers cannot receive allocation bounds checks because their type contains
  no allocation length, so indexing them requires explicit `unsafe`.

For foreign calls, `experiments.safety.ffi` supplies explicit checked contracts:

- non-null pointers;
- aligned pointer-plus-length buffers;
- nonnegative lengths;
- count × element-size overflow;
- bounded C-string termination;
- disjoint ranges for operations that forbid overlap.

These are boundary contracts supporting language safety, not a general FFI
ownership system.

## Build profiles

Import `experiments.safety.safety` in the entry module. Comprehensive checking
requires separate artifacts because sanitizer runtimes cannot be combined.

| Profile | Flags | Coverage |
|---|---|---|
| development | `--debug-runtime` | debug checks, ASan, stack canaries, indirect calls, crash diagnostics |
| illegal behavior | `--debug-checks --sanitize=undefined` | arithmetic, division, remainder, shifts, library bounds/invariants |
| races (supplemental) | `--debug-checks --sanitize=thread` | data-race diagnostics |
| initialization (supplemental, Linux) | `--debug-checks --sanitize=memory` | uninitialized-read diagnostics |

`scripts/safety-check.sh` emits separate instrumented objects for the principal
sanitizer profiles, proving that code generation—not only type checking—succeeds.
`scripts/safety-test.sh` verifies successful operations, runtime traps, and
compile-time failures.

## Explicit escape hatches

Unsafe intent must be visible and searchable:

- `unchecked-index`, `unchecked-load`, and `unchecked-store!`;
- `unsafe` marks one typed expression as exempt from this transform;
- raw alias loads/stores, arbitrary `llvm-ir`, raw `free`, and target
  register/control primitives require that marker;
- `allowzero-pointer` for an explicitly nullable/raw pointer;
- `unaligned-load` and `unaligned-store!` copy through aligned temporary storage;
- named truncating conversions from i64/u64 to narrower standard integers;
- wrapping and saturating arithmetic APIs.

The `unsafe` marker is the per-expression safety override. A broader per-scope
optimization-mode control would require compiler support.

## Non-goals

This project does not attempt to implement:

- file/thread/builder/transaction lifecycle protocols;
- general deadlock detection;
- application invariants;
- ownership, linear types, or a borrow checker.

ASan, MSan, and TSan remain useful supplemental build tools, but their findings do
not expand the language-safety metaprogram into those unrelated subsystems.
