# Coil heap inspector

## Native Typed But Live demo

The dedicated demo recreates the `live-but-static` particle sequence using the
ordinary Coil compiler and native REPL JIT. There is no bytecode VM. A native
Coil process owns the persistent `World`, checks ordinary s-expression Coil snippets,
compiles accepted generations to machine code, migrates struct state, and
executes every animation tick. The website is only the editor, tutorial, and
control surface; drawing happens in a separate AppKit/CALayer window.

From the repository root:

```sh
PATH=/path/to/current/coil/bin:$PATH ./scripts/native-live-demo.sh
```

To pin a particular compiler candidate instead of relying on `PATH`:

```sh
COIL=/absolute/path/to/coil-candidate ./scripts/native-live-demo.sh
```

Then open <http://127.0.0.1:7391/native-demo>. The numbered source presets cover
function replacement, defaulted struct fields, a rejected bool-to-enum edit,
an explicit field transition, enum dispatch, a rejected non-exhaustive match,
and repair. Rejected candidates remain visible with their compiler diagnostic;
the last accepted native generation and its state remain intact.

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
argument/monomorph selection layer. Imported-module catalogs remain a later layer;
native live redefinition is provided separately by the opt-in live controller below.

The endpoints are `GET /api/functions` and `POST /api/call/<id>`. Calls carry one
plain-text scalar per line in signature order. Function IDs are process-local and
stable for the lifetime of that process.

### Native live programming

Programs that initialize `experiments.heap-inspector.controller` gain a **Live
code** view and two additional endpoints: `GET /api/live` and `POST
/api/live/edit`. Ordinary inspected programs do not link the compiler; a small
callback registry advertises the capability only when the controller is present.

The native demo editor accepts normal s-expression Coil. A durable layout edit is
written directly against the current type:

```coil
(defsum Visibility (Hidden) (Visible))

(defstruct Particle
  [(visible Visibility (Visible))
   (hue i64 20)])

(migrate Particle visible old
  (if old (Visible) (Hidden)))
```

The controller retains the last accepted user source and injects private,
versioned historical declarations during expansion. Users never declare or name
old-layout implementation types. Each `migrate T.field(old)` becomes a checked
native function from the immediately preceding field type to the candidate field
type, plus a native whole-object adapter. Compatible fields copy, new fields use
declared defaults, and missing conversions reject the candidate as
`NeedsTransition`.

Each request contains only the submitted snippet. Successful snippets merge into
accepted history with last-definition-wins semantics. Rejected normal-Coil snippets
form a pending branch, so a later request can submit only the root-cause repair.

Edits use Coil's normal in-process checker and REPL JIT. The candidate image is
prepared without publication, its private commit entry registers exact schemas
and transition edges and builds shadow roots, and the controller publishes code
and roots only after the complete batch succeeds. A parse/type/transition error
keeps the accepted source and generation running. Root aliases block migration;
multi-version roots traverse every accepted edge in order.

This is native Coil, not a VM or interpreter. `letonce` declarations lower to
stable typed indirection cells and registered persistent roots. Structs and sums
carry stable nominal IDs plus exact versioned schema IDs; enum variant and payload
metadata is versioned alongside layouts. Live functions—including generic
functions after monomorphization—run as ordinary native Coil behind generated
read-side quiescence adapters.

Migration is a graph transaction. All affected roots and allocator-authorized
heap objects are converted into private storage before any address is published.
Sharing and cycles use a complete forwarding table. Direct pointers, array-element
pointers, and slices are rewritten by element index, so changing an element's size
does not corrupt an interior reference. Misaligned, unregistered, or out-of-bounds
references roll back the batch. Arrays transition elementwise through every exact
historical edge.

Inspector discovery alone never grants permission to move storage. The owning
allocator must install native allocate/release callbacks. Active aliases, borrows,
and FFI retains block migration with distinct states. Once staging begins, new
borrows, FFI retains, and frees are rejected until commit or abort. Transition
`abort` callbacks destroy uncommitted destinations; `retire` callbacks destroy
accepted old values and successful intermediate versions with the correct schema.

The edit endpoint accepts up to 1 MiB and reads the complete declared HTTP body.
It copies the candidate into an owned background job, returns `202 Accepted`, and
keeps status polling responsive; a concurrent submission receives `409 Conflict`.
The UI follows `Checking`, `Staged`, `WaitingForQuiescence`, `Migrating`, and the terminal state
instead of treating queue acceptance as publication.

Every native backend records current and retired generations. Images/engines that
introduce persistent static cells are pinned; unpinned retired generations are
reclaimed while the live writer gate proves no adapter frame is running. Explicit
generation leases cover escaped native callbacks, and non-null function pointers
stored in reflected persistent state acquire conservative leases automatically.
Reloadable function pointers themselves target permanent, signature-specific
trampolines backed by one-time static implementation cells; they never expose
reclaimable candidate text. Same-signature edits update an existing trampoline,
while a signature change creates a new ABI lineage and leaves the old callback
valid. Ordinary compiled modules can opt into this lowering with
`(reloadable-module)` after importing `coil.jit.reload`.
Reset and reclamation refuse to proceed while a lease is held. The live status API
reports retained generations, leases, persistent code escapes, and the most recent
reclamation count. It also reports the conservative complete-snapshot dependency
closure, root/object/schema/transition counts, and structured blocker metadata.

Long-running native loops can check `coil_live_reload_requested` at a safe
backedge and return to a stable outer driver. The poll never drops a read lease
in place, because doing so could leave an old-layout stack local alive across a
layout publication. Nested by-value struct edits propagate through containing
layout fingerprints and invoke exact native inner adapters. Defaults and explicit
transitions are both checked against the migration purity contract.

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

Run the complete windowed Doom integration from the repository root:

```sh
python3 scripts/c-doom-native.py --play --heap-inspector
```

The launcher builds the transformed module at `-O2`, starts Doom, waits for the
in-process viewer, and opens <http://127.0.0.1:7391/>. Plain windowed Doom remains
`python3 scripts/c-doom-native.py --play`. An occupied port is handled by choosing
the next free one; `--inspector-port N` selects a different preferred port.

This recovers exact record identity only where the C source retains a direct typed
allocation cast. Untyped `void *` dataflow cannot be reconstructed after lowering.
When a marker names one of the frontend's real explicit-layout Coil structs, the
inspector uses that declaration directly. It reports member names and offsets,
decodes integer, float, boolean, and pointer fields, and presents fixed arrays as
bounded inline byte values. Nested records, sums, and opaque foreign values remain
structural placeholders until reflection exposes enough qualified shape information
to generate their decoders safely.

Very large generated C modules can overflow an LLVM `-O3` optimization worker stack
independently of the inspector. Doom plus the inspector is verified at `-O2`; use
that level while the separate `-O3` LLVM pipeline limitation remains.

## Current files

- `transform.coil` — semantic discovery, allocator-boundary rewriting, metadata
  generation, and viewer boot injection.
- `runtime.coil` — census, synchronization, structured serialization, and legacy
  stdout/JIT query functions.
- `viewer.coil` — background localhost HTTP server and asset/API routing.
- `viewer/` — separate HTML, JavaScript, and CSS viewer assets.
- `controller.coil` and `live_api.coil` — staged JIT edit session and optional
  viewer bridge.
- `live_reader.coil` and `live_meta.coil` — exact live syntax, accepted-history
  injection, checked transition planning, and native adapter generation.
- `live.coil` — persistent roots, exact transition chains, shadow staging,
  quiescence gate, atomic publication, rollback, and alias accounting.
- `demo.coil` — typed allocations, inspection, snapshot, and free behavior.
- `viewer_demo.coil` — live heap values plus scalar functions used to exercise
  browser-side discovery and in-process invocation.
- `c_struct_demo.coil` — translated-C marker and explicit-layout value regression.
- `jit_demo.coil` — runtime query submission through Coil JIT.

## Optional inspector extensions

- Dynamic/segmented registry storage with recursion-safe bootstrap allocation.
- Rendering for all Coil scalar widths, slices, arrays, sums, nested values, and
  concrete generic field types.
- Allocator-instance identity and grouping in the viewer.
- Observable arena lifecycle/reset where an existing checked API provides it.
- Configurable bind address/port and authentication before non-loopback binding.
- Broader browser stress tests.
- Imported-module function catalogs, rich editors/renderers over the universal raw
  representation, and interactive generic monomorph selection. These extend the
  inspector UI; they are not alternate execution machinery for native live edits.

The architectural constraint remains fixed: this stays an opt-in transparent
metaprogram; none of it belongs in Coil core or `coil.alloc`.
