# Native Coil live metaprogram

Status: normative design and implementation contract. Phases A–E are implemented
and under direct native/JIT tests. Phase F remains open on bounded ARM JIT image
reclamation, and Phase G remains open on retained immutable-metaprogram expansion
latency. The incomplete gates are listed in the implementation audit below.

## Thesis

The live system is a metaprogram-generated native program. The user writes ordinary s-expression Coil. During the initial compilation, the live metaprogram recognizes opted-in definitions and rewrites them into the dynamic program that could have been written by hand:

- stable definition and type identities;
- version tables containing original source forms and checked metadata;
- stable function entry slots and permanent ABI trampolines;
- source-level dependency and reverse-dependency indexes;
- stable handles for live structs and versioned native payloads;
- generated constructors, accessors, tracers, destructors, and migration adapters;
- registered persistent roots and managed allocations;
- condition entries for broken code or missing migrations;
- restart boundaries and publication safe points;
- explicit JIT generation ownership.

The resulting application is ordinary native Coil. There is no bytecode VM and no alternate language. The existing Coil checker, monomorphizer, native JIT, and loader are backend services used to compile the small Coil closure emitted by the metaprogram.

## Non-negotiable invariants

1. **Stable source identity.** Every live definition receives a stable ID before lowering. Generated implementation names are metadata attached to that ID; nobody infers identity from a generated string.
2. **One coherent published world.** A thread observes one published live epoch. Function slots, schemas, roots, migrations, and dependency metadata change atomically.
3. **No ill-typed native entry.** Machine code is callable only after normal Coil checking. A broken definition is represented by a generated condition entry with its last accepted boundary ABI, not by executing ill-typed code.
4. **Stable live value boundary.** A live nominal value crosses an update boundary as a stable handle, never as an untracked by-value payload whose offsets may change.
5. **Old frames remain valid.** A native frame pins the code/schema epoch it entered. Publication never unmaps its code or rewrites values it is actively using.
6. **Tracked migration only.** Automatic migration touches registered handles, roots, containers, and references. Raw unregistered aliases block the edit rather than being guessed.
7. **Transactional failure.** Parse, expansion, checking, code generation, loading, migration, and validation may all fail without changing the published world.
8. **Single-definition input.** Scrubbing or editing a function submits that definition. A schema repair may submit a small explicit batch. The system computes and emits the affected closure; the editor never sends the entire program.
9. **Native GUI independence.** The AppKit renderer is an ordinary native host. The browser is only an editor/tutorial. Live semantics do not exist in JavaScript.
10. **No hidden fallback.** There is no value override, source replay, process restart, or browser-side simulation presented as live replacement.

## The three layers

| Layer | Owns | Does not own |
|---|---|---|
| Live metaprogram | identities, original forms, dependency graph, generated dynamic representation, transaction planning | native parsing/checking correctness or machine-code emission |
| Coil compiler/JIT | check emitted Coil closure, monomorphize, stage/load native image, resolve symbols | reconstruct user identity or decide live semantics |
| Generated runtime | slots, epochs, handles, roots, conditions, safepoints, migration, publication, leases | parsing arbitrary source or guessing dependencies |

A useful compiler API may expose resolved declaration IDs, exact types, or staged image control. Those are facts/services. The metaprogram remains the owner of the live model.

## Initial transformation and registries

### Definition discovery

The metaprogram walks the original top-level `Code` forms before reload lowering. For each `defn`, `defstruct`, `defsum`, `letonce`, export, and supported callback declaration it creates a stable `LiveDefId`. Identity is nominal within a live session and survives body/layout versions. The record retains the original normalized form, not generated Coil source.

```text
LiveDefinition
  id
  user_name
  kind: Function | Struct | Sum | Root | Migration | Export
  accepted_version
  accepted_original_form
  pending_original_form?
  declared_type_surface
  value_dependencies
  type_dependencies
  generated_artifacts[]
  status: Ready | Broken | NeedsMigration | Blocked
```

Original forms are stored structurally as owned `Code`/serialized syntax with source spans and hygiene context. Updating `radius` replaces the `radius` record. It does not append text to an accepted-program string.

### Dependency capture

Dependencies are captured while the metaprogram still sees original syntax and exact generated output:

- a resolved call adds `caller -> callee`;
- taking a function value adds a function-value dependency and an escape record;
- a parameter, return, local construction, match, field access, `sizeof`, array element, or generic specialization adds a type dependency;
- a struct field adds a by-value or reference containment edge;
- a `letonce` initializer adds root/type/constructor dependencies;
- a generated artifact is registered immediately against the source definition that caused it.

Compiler queries such as `code-decl`, `type-of`, checked declaration surfaces, and monomorph metadata can make these edges exact. If a query is missing, add that narrow compiler API. Do not recover edges by scanning generated symbol names.

The registry maintains forward and reverse indexes:

```text
calls[A]                 = {B, C}
called_by[B]             = {A}
uses_type[A]             = {Particle}
type_used_by[Particle]   = {A, radius, advance}
contains[World]          = {Particle}
contained_by[Particle]   = {World}
artifacts[A]             = {entry slot, impl v3, trampoline lineage 1}
```

### Generated function representation

For a stable function boundary the metaprogram emits:

1. a stable `FunctionRecord` keyed by `LiveDefId`;
2. one typed implementation slot per ABI lineage;
3. a permanent typed trampoline for function values and FFI escape;
4. a private implementation for each accepted version;
5. entry/exit accounting that pins the implementation generation;
6. a condition entry for a broken current version.

Direct calls in live code target the stable typed slot/trampoline generated for the source definition. Recursion and mutual recursion therefore resolve through already-created records; discovery happens before body rewriting.

A body-only edit with the same signature compiles one new private implementation and atomically replaces one slot. Existing frames finish in the old implementation. New calls enter the new one.

### Signature changes

A signature change creates a new ABI lineage; it never overwrites a slot with an incompatible pointer.

- The changed function and every source-level caller become dirty.
- Callers that can be rechecked against the new signature are rebuilt into the transaction.
- Callers that no longer typecheck receive a `Broken` entry at their existing callable boundary.
- First-class values and foreign callbacks on the old ABI continue to reference the old permanent lineage until explicitly retired or adapted.
- Publication changes the current definition version and all rebuilt caller slots atomically.

This supports “pause when reached”: unrelated code continues; entering a broken caller raises a typed live condition before any new body effects occur.

### Closures and function values

A closure is a stable handle containing a code-definition identity, ABI lineage, captured-environment schema/version, and payload handle. Editing a closure body updates its code lineage like any function. Changing capture layout is a struct evolution of the generated environment type. A raw JIT implementation address is never stored as a live function value.

### Generics and traits

The registry distinguishes a generic source definition from concrete native artifacts. It records every live monomorph and trait/dictionary artifact under the source `LiveDefId`. An edit dirties only instantiated dependents currently present, while future instantiations use the new accepted form. A layout change dirties monomorphs whose concrete ABI contains the changed type. Compiler monomorph metadata is an appropriate narrow compiler input here.

## Live structs: stable handles and versioned native payloads

The current crashing prototype allowed `Particle` and `World` to cross live boundaries as ordinary by-value native structs. That makes field offsets part of every dependent function and callback ABI. Recompiling almost everything can make it appear to work, but a single stale pointer is fatal. The proper dynamic program changes this representation deliberately.

### Public live representation

For an opted-in live struct `Particle`, the metaprogram gives live code a stable handle representation:

```text
LiveHandle<Particle>
  object identity / stable address
  current schema version
  pointer to versioned native payload
  ownership / borrow / pin state
```

Each accepted schema still has a real native payload layout:

```text
ParticlePayloadV1 { x, y, vx, vy }
ParticlePayloadV2 { x, y, vx, vy, hue, visible }
```

Generated constructors allocate a handle plus the current payload. Generated accessors, setters, match adapters, tracers, and destructors are typed native functions associated with an exact schema version. User code remains statically typed because the metaprogram rewrites source operations before checking; it does not expose erased bytes to user code.

This is still native Coil. The cost is an intentional indirection at live boundaries, comparable to an object reference. Non-live structs retain ordinary Coil by-value representation.

### What the transform rewrites

For a live struct, the metaprogram rewrites or generates:

- construction;
- field read/write;
- borrowing and reference creation;
- equality/debug/inspection adapters;
- arrays/slices/containers of live values;
- pattern matching where applicable;
- persistent roots;
- FFI boundary adapters;
- ownership/drop/trace operations.

No user function should contain an unregistered raw field offset to a live payload. Within an exact-version private implementation, the compiler may optimize repeated handle checks and use typed payload pointers while that version is pinned.

### Schema records

```text
LiveSchema
  type_id
  version
  original declaration
  fingerprint
  size / alignment / field offsets
  fields: stable field ID, name, checked type, default, ownership
  generated constructor/accessor/tracer/drop artifacts
  containing and contained type edges
  generation owner
```

Same-name adjacent fields retain identity. Rename requires explicit identity metadata; otherwise it is remove-plus-add. Returning to an old physical layout creates a new forward version, not time travel.

### Change classification

For each candidate field:

- same identity and representation-compatible type: copy/move;
- new field with checked pure default: default;
- changed field with an exact `migrate` edge: transition;
- removed POD field: drop nothing;
- removed owning field: staged destruction after commit;
- no sound source: `NeedsTransition`;
- raw alias/borrow/FFI escape prevents relocation: structured blocker.

Nested by-value types propagate layout dirtiness through `contained_by`. Handle/reference fields do not inherit payload layout changes, but their tracer/ownership contracts may still create semantic dependencies.

### Migration protocol

Migration is a shadow-graph transaction:

1. close the affected call gate and drain frames that hold exact-version payload borrows;
2. enumerate registered roots and managed handles for affected type identities;
3. allocate candidate payloads without changing handles;
4. traverse with a forwarding table to preserve sharing and cycles;
5. run exact typed adapters for every version edge in order;
6. rewrite tracked references, slices, container elements, and closure environments;
7. validate all candidate payloads, ownership, bounds, and root coverage;
8. atomically swap handle payload pointers and schema versions with function slots;
9. destroy old payloads only after successful publication and lease drainage;
10. on failure, destroy only candidate payloads and reopen the old gate.

The first implementation may eagerly migrate at publication. Lazy first-touch migration is possible later, but only if old frames and concurrent accesses obey the same version/borrow rules. Eager migration is the simpler native correctness baseline.

### Arrays, pointers, and aliases

- An array of handles is layout-stable; each object migrates through its handle.
- A packed array of payloads is a managed object with element schema/count and migrates elementwise.
- A slice is relocatable only when its base managed allocation, element identity, bounds, and interior offset are registered.
- A pointer into a live payload is a scoped borrow. It cannot cross a live safe point unless represented as a stable field/subobject handle.
- Integer-cast addresses and unregistered raw allocation aliases block automatic migration.
- Foreign-held payload pointers block migration unless the FFI registration provides relocation or uses stable handles.

### Sums and matches

A live sum also uses a stable handle/versioned payload when its representation can evolve. Adding a variant dirties every exhaustive match recorded by the metaprogram. A stale match becomes `Broken`; it is never compiled as a partial native switch. Variant migration maps old stable variant IDs to new variants and migrates payload fields using the same graph machinery.

## Edit transaction from source to native publication

### 1. Receive one edit

The editor sends one complete top-level definition or an explicit repair batch. Numeric scrubbing finds the enclosing original form and sends only that form. The runtime stores the candidate separately from the accepted registry.

### 2. Run the live metaprogram against the registry

The candidate is parsed as ordinary Coil syntax. The live metaprogram looks up stable identities, normalizes the form, computes candidate declaration surfaces, and updates a private transaction overlay. The accepted registry is immutable during planning.

### 3. Compute the affected closure

Seeds are the edited stable definition IDs. The closure includes:

- reverse source callers for function/signature changes;
- functions and roots that use changed types;
- containing types for by-value layout changes;
- exhaustive matches for sum changes;
- existing monomorphs and generated adapters;
- closure environment schemas;
- inspector/debug/trace/drop implementations;
- exports and callback adapters whose ABI or body depends on an affected definition.

This computation operates entirely on metaprogram-owned stable IDs and exact edges recorded during earlier transformations.

### 4. Re-run transformation on original forms

For every dirty source definition, use its retained original form (candidate form for edited IDs, accepted form for dependents) and transform it against the candidate registry overlay. Generate a small ordinary Coil module containing only:

- candidate schemas and historical layouts needed for exact transitions;
- dirty private function implementations and any new ABI lineages;
- generated adapters/conditions/migrations;
- a private transaction entrypoint;
- declarations for stable runtime slots/handles supplied by the host.

No complete accepted-source string is constructed.

### 5. Check normally

Coil expands, resolves, infers, and checks the emitted closure. Outcomes are structured by source `LiveDefId`:

- all valid: continue staging;
- a dirty function invalid: generate/publish a `Broken` condition entry if its old boundary remains representable;
- invalid transition/default or inconsistent registry mechanics: keep candidate pending;
- compiler/JIT failure: rollback.

For the tutorial’s pedagogical policy, a schema edit with a missing migration is shown immediately as `NeedsTransition` and the native demo pauses. The general runtime may keep unrelated actors running until they reach a broken entry.

### 6. Stage native image

Load the new machine code into an unpublished generation. Resolve every expected artifact by the exact generated-artifact records created in step 4. Validate slot ABI fingerprints; no textual signature or symbol-prefix inference is allowed.

### 7. Quiesce and migrate

Request an affected-epoch safe point. New affected calls wait at their stable gates. Existing frames finish or return at transform-inserted polls. Drain scoped borrows and callbacks, then build the shadow migrated graph.

### 8. Atomic publication

Under the live-world commit lock:

- advance the epoch;
- publish new schemas and transition edges;
- swap migrated handle payloads/root handles;
- batch-swap implementation slots and current ABI lineages;
- publish Ready/Broken status records and diagnostics;
- publish the candidate original forms/dependency overlay.

A reader sees the old tuple or new tuple, never a mixture.

### 9. Retirement

Each frame/callback/escaped function value holds a generation or ABI-lineage lease. Retire old machine code, schema metadata, and payloads only when all relevant leases and borrows reach zero. Stable trampolines and stable handles have session lifetime.

## Conditions, pause, repair, and native resume

Normal native Coil cannot preserve and rewrite an arbitrary machine stack like the VM prototype’s heap frames. The metaprogram therefore creates explicit restart boundaries.

- A live function entry is a condition boundary before user effects.
- Event callbacks, animation ticks, actor turns, and opted-in loop polls are restart boundaries.
- A Broken entry or missing migration raises a structured condition to the nearest boundary.
- The boundary quarantines/discards the in-flight turn, preserving the last committed persistent state.
- The editor repairs the source definition or transition.
- After a successful transaction, the boundary reruns that function call/tick from its saved typed arguments or host event.

This is honest restart semantics, not arbitrary instruction-level continuation. Code that needs finer resume granularity must introduce explicit transactional/checkpoint forms that the metaprogram lowers into heap-resident restart records. Irreversible effects require prepare/commit/abort hooks or make a boundary non-restartable.

## Scenario matrix and required behavior

### Functions

| Scenario | Generated behavior |
|---|---|
| Same signature, body changes | Compile one private implementation; swap one typed slot next frame |
| Syntax/type error in body | Accepted implementation remains; pending diagnostic, or publish Broken entry under deferred policy |
| Callee body changes | Callers need not rebuild because calls cross stable slot |
| Callee signature changes | New ABI lineage; recheck/rebuild reverse callers transactionally; incompatible callers become Broken |
| Direct recursion | Private body calls stable record for same source ID; new recursive calls select current epoch |
| Mutual recursion | Predeclare all records, then transform bodies; publish slot batch atomically |
| Function value stored in state | Store permanent typed trampoline/lineage handle, never implementation address |
| Closure capture changes | Version/migrate generated closure-environment live struct |
| Generic edit | Dirty live monomorph artifacts; future monomorphs use new source version |
| Trait method/impl edit | Dirty dictionaries/vtables and their consumers by stable impl/method IDs |
| Removed function | Current entry becomes Removed/Broken; old pinned frames and old ABI handles remain valid until retired |

### Types and state

| Scenario | Required behavior |
|---|---|
| Add POD/defaulted field | Derive migration; preserve handle identity and other fields |
| Add field without default | NeedsTransition; no publication |
| Reorder fields | New native payload layout; copy by stable field identity, not bytes |
| Remove POD field | Omit it in candidate payload |
| Remove owning field | Stage drop; execute only after commit |
| Change field type | Require exact checked transition unless a safe built-in coercion is specified |
| Nested by-value change | Propagate through containing payload schemas and dependent exact-version code |
| Change referenced object type | Handle layout stays stable; semantic/accessor dependencies still recheck |
| Add enum variant | Invalidate exhaustive matches; missing arms become Broken/rejected |
| Remove/map enum variant | Require variant transition for live values of removed variants |
| Multiple sequential changes | Preserve an ordered vN→vN+1 migration chain; multi-hop objects traverse every edge |
| Revert physical layout | Create a new forward version and edge |
| Cyclic/shared graph | Forwarding table preserves cycles and object identity |
| Managed array/slice | Migrate elements and adjust tracked bases/offsets/bounds |
| Raw pointer or foreign alias | Block with a precise registration-site diagnostic |

### Native frames and concurrency

| Scenario | Rule |
|---|---|
| Old frame executing body-only function | Finish on pinned old implementation; new calls use new slot |
| Old frame holds exact payload borrow | Schema publication waits until exit/poll releases it |
| Long-running loop | Transform inserts or requires an explicit live poll at a safe backedge |
| Multiple application threads | Epoch gate parks only affected callers; unrelated work may continue |
| Concurrent edit requests | Single transaction planner; later edit queues against either accepted or explicitly pending branch |
| Migration failure | Cancel shadow graph, reopen old gates, preserve accepted epoch |
| Process receives edit during migration | Queue it; never mutate the transaction overlay concurrently |

### FFI and native GUI

The host receives permanent C-ABI trampolines whose addresses never belong to a reclaimable implementation image. A trampoline resolves a stable source definition and ABI lineage, acquires a lease, calls the current implementation, and releases the lease.

- Body edits are transparent to the host.
- A user-level signature change does not mutate an exported C ABI.
- Changing an export ABI requires a new trampoline and explicit host re-registration protocol.
- Callback arguments/results that contain live nominal types cross as stable handles or explicitly frozen foreign representations.
- AppKit thread-affinity remains host policy: publication may stage off-thread, but UI calls continue on the main thread.

For the bouncing-ball demo, the native window keeps stable `tick()` and query callback trampolines. Their bodies may change, but their host ABI and address do not. The persistent `World` is a registered stable handle graph. No callback ever retains a private JIT implementation pointer.

## Inspector/editor contract

The status surface reports facts from the live registry:

- accepted and pending source definition versions;
- stable IDs and source-level affected closure;
- Ready/Broken/NeedsTransition/Blocked state;
- diagnostics attached to original forms/spans;
- staged/published epoch;
- schema versions and migration edges;
- registered roots, managed objects, borrows, raw/FFI blockers;
- active calls and generation/ABI-lineage leases;
- migration and publication timing;
- last observed native frame epoch.

The editor sends forms and renders state. It never decides dependencies, mutates values directly, or predicts acceptance.

## What must be removed from the current prototype

The following are explicitly non-normative and must be deleted rather than extended:

- accumulating accepted function source into a program snapshot;
- replaying a complete accepted source wrapper for schema changes;
- compiler-side `ReplLiveDefinition` source reconstruction added during the latest attempt;
- mapping generated names back to source definitions with `name--…` conventions;
- deciding function edits by controller substring searches;
- retaining a generation forever as a substitute for correct artifact leases;
- publishing raw callback implementation pointers;
- allowing live by-value payloads to cross stable callback/function boundaries;
- claiming `incremental-typed-closure` in status without exposing the actual stable-ID closure.

The valid existing work to preserve includes transition syntax/checking, schema version records, staged migration and rollback machinery, persistent root tracking, JIT prepare/commit separation, stable statics, typed reload cells, native GUI/editor separation, and the crash regressions already discovered.

## Minimal compiler/JIT APIs that are legitimate

The metaprogram may need narrow facilities, but none owns the live architecture:

1. Query resolved declaration identity for a `Code` node.
2. Query the checked type/declaration surface for original syntax.
3. Query concrete monomorph artifacts produced for a source definition.
4. Run a retained metaprogram transform against one submitted form with session-owned state.
5. Check/monomorphize an emitted closure against accepted imports/declarations without reparsing providers.
6. Stage a native image, enumerate exact requested symbols, commit or discard it.
7. Retain/release/reclaim a JIT generation.
8. Return structured diagnostics and source spans.

If current Coil cannot persist the live metaprogram’s registry across submissions, expose an explicit metaprogram-session state object. Do not replace it with accepted-source concatenation.

## Implementation sequence

### Phase A — registry and transform contract

- Define stable IDs and registry records in Coil.
- Discover all source definitions before rewriting bodies.
- Store owned original `Code` forms.
- Record generated artifacts directly.
- Record exact source-level call/type/root/export edges.
- Add registry inspection tests independent of JIT.

Gate: transforming the demo produces a deterministic registry where `demo_tick` is linked directly to its generated trampoline and its `World`/callee dependencies, with no generated-name parsing.

### Phase B — correct function dynamics

- Generate permanent entry slots/trampolines and private implementations.
- Cover direct calls, recursion, mutual recursion, function values, callbacks, and closures.
- Implement ABI lineages and Broken entries.
- Compile a single edited function from its registry form.

Gate: 1,000 body scrubs install only `radius`; type errors preserve accepted code; cross-function dispatch and callback values follow the slot; retired images are reclaimed under stress.

### Phase C — live handle representation

- Transform opted-in struct construction/access/borrow/drop.
- Generate stable handles and exact-version payload schemas.
- Convert `letonce World` and particle storage to registered handle graphs.
- Prohibit untracked payload pointers at live boundaries.

Gate: the base demo runs natively with the transformed representation before supporting any layout edit.

### Phase D — schema transactions

- Diff schemas by stable field/variant identity.
- Generate copy/default/transition adapters.
- Compute source-level affected closure from registry edges.
- Stage native closure and shadow migration graph.
- Atomically publish handles, roots, schemas, and slots.

Gate: every struct/sum scenario in the matrix succeeds or produces the specified pending/blocker state without process failure.

### Phase E — conditions and restart

- Generate Broken/NeedsMigration condition entries.
- Add tick/callback/actor restart boundaries and loop polls.
- Quarantine in-flight state and rerun after repair.
- Specify effect hooks and non-restartable diagnostics.

Gate: reproduce the original Live & Typed repair story in native Coil: broken function reached → pause; function repaired → rerun; missing migration reached → pause; migration supplied → commit; no process restart.

### Phase F — concurrency, FFI, and lifetime

- Affected gates, epoch pinning, borrow drainage, callback leases.
- Permanent C trampolines and host re-registration rules.
- Precise generation/payload retirement.
- Thread, allocator-failure, and alias stress.

Gate: sanitizers and long-running native GUI stress show no stale calls, use-after-free, partial epochs, or leaked unbounded generations.

### Phase G — latency

Correctness comes first, but the target remains next-frame body edits. Measure parse, metaprogram transform, checking, mono, native emission, load, commit, and first observed frame separately. Cache immutable imports/metaprograms and compile only emitted closure artifacts. Schema edits may take longer and show an explicit staged state; body scrubs must not.

## Required final validation

- Full seven-step bouncing-ball tutorial with expected two repair states.
- Same persistent World identity/positions across accepted edits.
- Function scrub reaches the next native frame; no browser override.
- Apply submits the visible snippet/batch, never the whole program.
- Exact affected source IDs visible in status.
- Add/reorder/remove/change/nested/revert struct tests.
- Add/remove/change enum and exhaustive-match tests.
- Recursion, mutual recursion, signature change, closure, generic, trait, and function-value tests.
- Raw pointer, slice, borrow, FFI, and ownership blocker tests.
- Rollback injected at every transaction stage.
- Multi-hop sharing/cycle migration tests.
- Concurrent edits/calls and cooperative loop drainage.
- Callback address stability and generation reclamation.
- ASan/TSan where supported, repeated compiler fixpoint, `git diff --check`, and no Python production path.

## Current implementation audit

The implementation follows the ownership boundary in this document: original
source identity, dependency closure, artifacts, typed slots, live schemas, Broken
state, and publication planning are all generated or retained by the Coil
metaprogram. The controller submits source and drives prepared transactions; it
does not parse definitions or reconstruct compiler symbol names.

Proven gates:

- deterministic source/artifact/dependency registries independent of the JIT;
- definition-sized function updates, ABI lineages, direct/recursive/first-class,
  closure, generic, trait, and erased-trait dispatch;
- stable handles, nested handle ownership, struct and sum migration, rollback,
  reference rewriting, aliases, borrows, FFI retention, and allocator ownership;
- per-source affected gates, structured conditions, native restart boundaries,
  transitive Broken propagation before caller effects, and repair without a VM;
- the exact seven-step native bouncing-ball tutorial with persistent coordinates
  through NeedsTransition and Broken repair states;
- serialized macOS-window/HTTP frame transactions, including restart-safe lock
  release, under normal and TSan testing.

Open gates that prevent a completion claim:

1. ARM JIT edit images containing permanent `repl_static` storage are pinned as a
   whole image. Exact generation leases exist, but 1,000-edit bounded reclamation
   cannot pass until static storage ownership is separated from reclaimable code.
2. A definition-sized edit currently measures about 1.05 seconds. Roughly 0.9
   seconds is repeated expansion of immutable imported metaprograms. The retained
   compiler session needs an explicit cache/reuse API before next-frame scrubbing
   is true.
3. The final long-running native GUI stress, complete transaction-stage fault
   injection matrix, repeated compiler fixpoint, and final ASan/TSan sweep remain
   to be completed after those two compiler/JIT boundaries are available.

**Generated native live program**

![Generated native live program](coil-live-metaprogram-design_files/graph-ccenycpqa2y.png)
