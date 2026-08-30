# Manual live migration

This package is a from-scratch, non-metaprogrammed proof of the runtime protocol
needed for native live schema evolution. It intentionally does not import the
heap-inspector live runtime or reader transform.

The implementation exposes every operation directly: schema and dependency
registration, tracked allocation, stable handles, roots, reader leases,
stop-the-world publication, two-pass graph copying, rollback, and JIT generation
publication. Once this protocol is demonstrably correct, a metaprogram can be
evaluated as a generator for these calls.

The `meta.coil` follow-up now performs that evaluation in deliberately small
layers. It generates physical versioned structs and exact schema/reference
metadata, explicit dependency registrations, and type-checked compatible
migrations. It does not replace the runtime protocol: its expansions call the
same registration and transactional migration API as the handwritten baseline.

## Run

From the `coil-experiments` root:

```sh
coil build src/experiments/manual-live/main.coil -o build/manual-live
./build/manual-live

coil build src/experiments/manual-live/meta_schema_test.coil -o build/manual-live-meta-schema
./build/manual-live-meta-schema
coil build src/experiments/manual-live/meta_dependency_test.coil -o build/manual-live-meta-dependency
./build/manual-live-meta-dependency
coil build src/experiments/manual-live/meta_migration_test.coil -o build/manual-live-meta-migration
./build/manual-live-meta-migration
coil build src/experiments/manual-live/meta_jit_test.coil -o build/manual-live-meta-jit
./build/manual-live-meta-jit
coil build src/experiments/manual-live/meta_policy_test.coil -o build/manual-live-meta-policy
./build/manual-live-meta-policy
coil build src/experiments/manual-live/meta_collection_test.coil -o build/manual-live-meta-collection
./build/manual-live-meta-collection
coil build src/experiments/manual-live/meta_abi_test.coil -o build/manual-live-meta-abi
./build/manual-live-meta-abi
coil build src/experiments/manual-live/blocked_jit_test.coil -o build/manual-live-blocked-jit
./build/manual-live-blocked-jit
```

The V3 transaction intentionally fails during native publication, so the JIT
prints its rejection diagnostic. A successful run then prints:

```text
manual-live: dependency closure=3, v1=30, v2=32, rollback=v2
```

and exits zero.

The focused metaprogram executables are silent and exit zero. The JIT test is
the end-to-end proof: each version is a separate source submission. Inside each
submission, macro expansion generates the physical schema, registrations,
dependency edges, and (for V2) migration function. The prepared JIT entry calls
those generated registrars against the host runtime, migrates the two-node
cycle, and publishes generated V2 code whose result is 32.

## What the metaprogram proof establishes

The four focused tests compare generated artifacts with the explicit protocol:

1. generated sizes, alignments, versions, logical IDs, and reference offsets
   match independently handwritten registrations;
2. generated dependency edges produce the expected reverse closure;
3. generated migration code preserves stable handles and cyclic references
   while copying compatible fields and initializing added fields;
4. the same forms expand inside isolated JIT submissions and safely register
their artifacts with the persistent host runtime.

## Deferred function errors

`blocked.coil` and `blocked_meta.coil` prove function-boundary error deferral.
`live-blockable-function` takes a checked parameter/return header and generates a
permanent typed gate plus stable `BlockedFunction` cell. A rejected body publishes
the cell's `Blocked` state and diagnostic identity. Calls park on a generation-
counted event without losing notifications; their typed native frames retain the
original arguments. A same-ABI repair publishes its native address, wakes every
waiter, and the gate invokes that implementation exactly once.

`PartialGeneration` requires every definition in the exact reverse dependency
closure to have either `Ready` or `Blocked` coverage for the same candidate epoch;
an old implementation or a result from another epoch cannot satisfy the gate.
`blocked_jit_test.coil` stages a valid three-variant sum, observes a genuinely
non-exhaustive dependent match fail JIT checking, proves the type cannot publish
while that dependent is missing, installs a typed blocked artifact, publishes the
partial type generation, parks a real pthread call with argument `41`, repairs the
function through JIT, and observes the original invocation return `42`. A second
generated `(bool, i64) -> i64` gate proves the mechanism is signature-generated,
not hardcoded to the first ABI.

The current proof requires a valid function header and a controller decision to
convert a failed body into `Blocked`; the stock Coil checker still reports the
body error normally. Automatic extraction of a recoverable checked header from a
failed definition is compiler/JIT orchestration work. `void` gates, cancellation,
owned-argument cancellation/drop, and resuming inside an already-started function
are deliberately not claimed yet.

The policy layer goes further:

- `live-struct-auto` derives physical fields and self-reference metadata from a
  single annotated field list;
- `live-transition-auto` derives compatible copies, cyclic-reference rewrites,
  and added-field defaults by comparing old and new field declarations;
- non-scalar fields are accepted through exact `LiveValue` trait resolution,
  rather than a collection-name allowlist; unsupported borrowed/owning types and
  changed field types still fail compilation;
- `ArrayList T` implements the protocol recursively when `T: LiveValue`: prepare
  clones independent backing storage, abort destroys only the candidate clone,
  commit retires the old list, and final runtime destruction retires the accepted
  clone;
- borrowed `(slice T)` fields are registered as reference metadata rather than
  owners. `ArrayList` cloning contributes an old-range to new-range relocation;
  the second pass preserves a slice's interior byte offset and element length,
  rejecting unknown, ambiguous, or out-of-bounds ranges transactionally;
- `live-function-versioned` emits distinct native names and candidate-address
  artifacts for each version;
- the ABI test keeps `(i64) -> i64` and `(bool) -> i64` lineages in separately
  typed slots, proving a signature edit does not overwrite an incompatible slot;
- the JIT test retains one exact generation token for every stored callback:
  schema validation/destruction, transition application, and published code.
  All seven leases are released only after runtime metadata is destroyed.

`semantic_policy.coil` and `semantic_transform.coil` implement exact dependency
derivation after resolution. Source registrars associate stable numeric IDs with
functions/types directly; the pass uses `code-decl`, `binding-of` information,
and `type-of` to emit call/type edges without scanning generated names. The
`manual-live-semantic` package installs a semantic checker that requires exactly
the expected three edges, and its workspace-configured check passes. The same
transform now runs inside each standalone JIT submission in `meta_jit_test.coil`
and `meta_abi_test.coil`; no prior accepted source is replayed.

`meta_collection_test.coil` forces validation failure after cloning an owned
list and proves the old list and its interior borrowed slice remain accepted. It
then proves an out-of-bounds borrowed range rejects publication, followed by a
successful migration where the list has independent backing storage and the
slice points at the same interior element range in that new storage. Runtime
teardown destroys only the published owner.

This proves automatic source analysis for direct resolved calls and concrete
type uses, plus safe automatic policy for scalar/self-referential and trait-managed layouts. Stable
logical IDs and defaults remain declarations of intent; they are not facts a
compiler can infer safely.

During the proof, a generated runtime registrar accidentally used
`primitive/error`, which correctly made its native caller metaprogram-only. That
was initially mistaken for an explicit-file transform ordering problem. The
registrar now returns an ordinary nested status value; the mistaken compiler bug
report is retracted, and explicit-file plus in-JIT semantic transforms both pass.

## Demonstrated protocol

The host manually registers one logical `Node` type, two dependent functions,
and the reverse edges `cycle-total -> node-value -> Node`. Two tracked nodes
form a cycle and are reachable through named roots and stable handles.

The run proves:

1. the reverse dependency closure contains exactly the changed type and both
   dependent functions;
2. V1 code is compiled by the in-process JIT and installed in a stable host
   function slot;
3. an escaped payload borrow blocks relocation without changing accepted data;
4. V1 -> V2 allocates the entire shadow graph before rewriting references, so
   the cycle survives and stable handle addresses do not change;
5. candidate validation runs against the complete rewritten shadow graph;
6. V2 code and V2 data publish through the same prepared JIT transaction;
7. the host function slot transfers an exact JIT generation lease from V1 to
   V2 before reclamation;
8. the deliberately failing V2 -> V3 migration frees candidate allocations,
   rejects candidate machine code, and leaves V2 code and data callable.

## Deliberate restrictions

This baseline uses fixed-capacity registries so allocation of runtime metadata
cannot recursively enter the tracked heap. Every migratable allocation must be
created with `handle-new!`; arbitrary raw pointers cannot become persistent live
references. Typed payload pointers are valid only inside a reader epoch or an
explicit borrow. Physical layouts and implementation functions have versioned
native names; stable identity lives in handles, logical IDs, dependency records,
and the host function slot.

These restrictions are correctness boundaries, not conveniences to be silently
relaxed by the future metaprogram.
