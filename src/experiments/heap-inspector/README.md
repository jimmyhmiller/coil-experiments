# Coil heap inspector

An opt-in whole-program metaprogram that adds a live allocation inspector to an
ordinary Coil program. It borrows the product shape of `lang-with-inspector`—a
viewer attached to a running process—but follows Coil's allocator-oriented memory
model rather than adding managed objects, per-type arenas, or garbage collection.

```sh
coil build app.coil -o app --use experiments.heap-inspector.transform
./app
# heap inspector: http://127.0.0.1:7391
```

The application source, Coil compiler, and standard library are unchanged. Removing
`--use` removes the census, generated metadata, server, and viewer.

## Contract

The inspector sees every successful operation made through the checked
`coil.alloc` protocol boundary: `raw-alloc`, `raw-resize`, `raw-remap`, and
`raw-free`.

The transform recognizes checked declarations, not names or import spellings. It
rewrites the boundary calls inside the checked `coil.alloc` module for this build,
so `alloc`, `alloc-bytes`, `create`, `box`, `free`, `resize`, `remap`, `reallocate`,
collection backing storage, and custom `Allocator` implementations flowing through
those APIs are covered without enumerating convenience functions.

Each user module also receives a lazily initialized catalog for its concrete struct
declarations. This lets runtime type IDs from generic collection storage—such as
`(ArrayList Project)` allocating inside the standard library—resolve back to qualified
names and field layouts even though the concrete allocation call is not written in the
user module.

This is deliberately not a global hook in Coil and does not modify `coil.alloc` on
disk. It is an orthogonal compilation transform.

> Every live allocation made through the transformed program's `coil.alloc`
> protocol is enumerable. Memory obtained directly from libc, a foreign library,
> `primitive` allocation, stack/static storage, or another bypass is not.

## Viewer and query model

The transform injects a localhost HTTP server into `main`. The viewer polls a
structured snapshot containing:

- live allocation ID and address;
- process-local typed allocation ID;
- element count, byte size, and alignment;
- concrete struct name, size, alignment, and field layout when statically known;
- generated values for i64, bool, f64, and pointer fields;
- raw allocation records even when structured type metadata is unavailable;
- total live allocation count and bytes.

The JSON endpoint is `GET /api/snapshot`. The HTML viewer is `GET /`. The UI is
ordinary, separately maintained `index.html`, `app.js`, and `style.css` under
`viewer/`; Coil only serves those files. Set `COIL_HEAP_INSPECTOR_VIEWER` to that
directory when the program runs from somewhere other than the repository root.

The viewer provides a live allocation/byte history, searchable type navigation,
a size-weighted address map, sortable allocation census, type-layout memory map,
raw-byte display, and a focused value inspector. Polling pauses while the tab is
hidden and can also be paused explicitly from the toolbar.

### Live functions

The **Functions** view reflects every concrete top-level function from the entry
module and renders an inline invocation form for each one. Clicking **Run** executes
the already-compiled Coil function inside the inspected process, then refreshes the
heap snapshot. This is a direct typed call through a generated adapter, not an eval
VM, JIT session, subprocess, or erased calling convention.

`i64`, `bool`, and `f64` use readable controls and JSON values. Every other concrete
sized Coil value—including narrower integers, structs, sums, arrays, slices,
pointers, and function pointers—uses its exact in-memory byte representation as the
universal fallback. Raw arguments are entered as little-endian hex and raw results
carry their type, size, and complete byte sequence. This makes the callable surface
complete without inventing ownership or constructors for types the inspector does
not yet understand. Rich recursive editors and structured result rendering can be
layered over the same typed adapters later.

`main` is omitted because recursively entering the program entry point is not a
meaningful live operation. Uninstantiated generic definitions still require a type
argument/monomorph selection layer. Imported-module catalogs and live code
redefinition are also later layers; the current registry describes the entry
module's concrete callable surface.

The endpoints are `GET /api/functions` and `POST /api/call/<id>`. Calls carry one
plain-text scalar per line in signature order. Function IDs are process-local and
stable for the lifetime of that process.

### Byte buffers and slice references

Selecting any live allocation opens a paged hex and ASCII memory explorer. The
viewer reads at most 256 bytes per request, so large `u8` buffers can be explored
without copying their entire contents into every snapshot. Addresses and offsets
are read while the registry lock proves the allocation is still live.

The snapshot also derives slice references from direct `slice` fields in reflected
live heap objects. For each reference it reports the target allocation, interior
offset, length, source allocation, source type, source slot, and field name. The
viewer highlights covered bytes and lets a reference jump directly to its target
offset. Multiple slices may overlap or point into the same allocation.

This reference list is intentionally described as **discovered slices**, not all
slices. Allocator interception provides a complete census of allocations made
through the transformed `coil.alloc` boundary, but it cannot enumerate slice
descriptors that exist only on a stack or in registers. Direct fields in known
heap layouts are discoverable; slices hidden in foreign, unreflected, or nested
container layouts require additional reflected traversal rules before they can be
reported. The underlying byte-buffer allocation remains authoritative even when
no slice reference is discoverable.

Allocation IDs are monotonically increasing and never reused. A successful free
retires the record before the underlying allocator can reclaim or reuse its address.
Resize updates the existing record. Remap preserves its allocation ID while changing
the address and request metadata.

## Consistency and threading

Registry changes and snapshots use a static-storage spin mutex implemented with
`coil.atomic`. Census bookkeeping remains in static storage. The serialized response
uses a reusable geometrically growing buffer owned by the inspector runtime, which
the transform excludes from observation, so it cannot recursively enter the census.
Free cannot race a snapshot into dereferencing reclaimed
storage: it must retire the entry under the same lock before delegating.

The snapshot currently has **weak field consistency**. Ordinary program writes do
not take the registry lock, so fields from a concurrently-mutating allocation may
come from slightly different instants. The allocation itself remains valid for the
duration of serialization. This is appropriate for an observational Coil tool and
does not impose a stop-the-world protocol on programs. A later opt-in quiescence
policy can strengthen field consistency without changing the allocator census.

The registry is intentionally bounded at 4,096 allocation events, 256 reflected
types, and 4,096 fields. Capacity exhaustion drops new census records rather than
writing out of bounds. The JSON response buffer grows as needed and has no fixed
snapshot-size ceiling.

## Coil-specific semantics

This is an allocation inspector, not a language object browser:

- Typed slices are one allocation with `count > 1`, not many objects.
- `alloc-bytes` has type ID zero and is shown as raw bytes.
- Pointer fields are edges/addresses; ownership is not inferred.
- Struct metadata is generated where the checked program exposes a concrete struct
  allocation type.
- A bump arena may accept logical frees while retaining physical storage. The census
  records protocol liveness: after `raw-free`, the allocation is no longer live even
  if that allocator retains its backing bytes.
- Arena bulk reset performed outside the allocator protocol cannot be observed.

There is no garbage collector, reachability analysis, tracing root set, moving
objects, or hidden ownership model.

## Translated C programs

The C frontend can preserve allocation facts that its ordinary lowering erases.
It emits an identity marker around direct casts from `malloc`, `calloc`, `realloc`,
or `Z_Malloc` to a named record pointer. Without the inspector metaprogram the
marker simply returns its pointer, so it has no allocation policy or global hook.
With the inspector enabled, the transform consumes the marker and associates the
live region with the C record name, size, alignment, and derived element count.

The transform also wraps translated calls to the four libc allocation functions.
Doom's zone allocator needs one additional boundary: `Z_Malloc` subregions are
registered and `Z_Free` retires them because the surrounding zone is one large libc
allocation. This is still a transparent, opt-in metaprogram; Coil's allocator and
standard library are unchanged.

This recovers exact record identity only where the C source retains a direct typed
allocation cast. Untyped `void *` dataflow cannot be reconstructed after lowering.
When a marker names one of the frontend's real explicit-layout Coil structs, the
inspector uses that declaration directly. It reports member names and offsets,
decodes integer, float, boolean, and pointer fields, and presents fixed arrays as
bounded inline byte values. Nested records, sums, and opaque foreign values remain
structural placeholders until reflection exposes enough qualified shape information
to generate their decoders safely.

Very large generated C modules can overflow an LLVM `-O3` optimization worker stack
independently of the inspector. Build those artifacts with `-O0` while that LLVM
pipeline limitation remains; the metaprogram and explicit-layout metadata work at
that optimization level.

## Current files

- `transform.coil` — semantic discovery, allocator-boundary rewriting, metadata
  generation, and viewer boot injection.
- `runtime.coil` — census, synchronization, structured serialization, and legacy
  stdout/JIT query functions.
- `viewer.coil` — background localhost HTTP server and asset/API routing.
- `viewer/` — separate HTML, JavaScript, and CSS viewer assets.
- `demo.coil` — typed allocations, inspection, snapshot, and free behavior.
- `viewer_demo.coil` — live heap values plus scalar functions used to exercise
  browser-side discovery and in-process invocation.
- `c_struct_demo.coil` — translated-C marker and explicit-layout value regression.
- `jit_demo.coil` — runtime query submission through Coil JIT.

## Remaining production work

- Dynamic/segmented registry storage with recursion-safe bootstrap allocation.
- Rendering for all Coil scalar widths, slices, arrays, sums, nested values, and
  concrete generic field types.
- Allocator-instance identity and grouping in the viewer.
- Observable arena lifecycle/reset where an existing checked API provides it.
- Configurable bind address/port and authentication before non-loopback binding.
- Browser and concurrency stress tests.
- Imported-module function catalogs, rich editors/renderers over the universal raw
  representation, generic monomorph selection, invocation coordination with
  application threads, and opt-in live redefinition through Coil's typed `Var`
  machinery.

The architectural constraint remains fixed: this stays an opt-in transparent
metaprogram; none of it belongs in Coil core or `coil.alloc`.
