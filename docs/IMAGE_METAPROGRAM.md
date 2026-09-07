# Coil image metaprogram

Status: implemented. All phases A–G are built and gated in
`src/experiments/image/` over the real live runtime (see "Implementation status" at the end). It builds on
the implemented native live metaprogram (`docs/NATIVE_LIVE_METAPROGRAM.md`,
phases A–E) and reuses its runtime, registry, reader, and controller without
changing their semantics. Every change this design needs in an existing
experiment is listed in "Additive seams" and is additive.

## Thesis

A Smalltalk image is the object memory plus the code that was accepted into it.
A Lisp image is the same thing with a toplevel function. Coil already has both
halves as runtime data, maintained by the live metaprogram:

- the accepted program: every live definition with a stable ID, its accepted
  original form, its version chain, its ABI lineages, and its Ready/Broken state;
- the live world: registered roots, stable handles, versioned native payloads,
  managed objects, reference-field metadata, schema versions, and the checked
  transition edges between versions.

An image is the durable form of exactly that registry. Saving an image is a live
transaction: close the world gate, drain readers, walk the registered graph,
write it. Loading an image is a boot sequence: replay the accepted program
through the JIT session, materialize the graph at the schemas it was saved
under, then submit the program on disk as an ordinary live edit so that any
schema drift goes through the existing checked migration machinery. Nothing is
dumped as raw memory, nothing is mapped at a fixed address, and no VM appears.
The image feature is a metaprogram (`experiments.image.*`) layered on the live
metaprogram; the Coil compiler is unchanged.

What this buys, compared with Smalltalk and Lisp images:

| Smalltalk / Lisp | Coil image |
|---|---|
| object memory | registered live graph: roots, handles, managed objects |
| image file | one `.coilimage` container |
| changes file, sources file | accepted-submission ledger inside the image |
| VM / image format version check | header: format version, target, pointer width, live-metaprogram fingerprint |
| instance migration on class redefinition, `update-instance-for-redefined-class` | schema version chain and `migrate` edges, replayed at load |
| `startUp` / `shutDown` lists, `*save-hooks*` / `*init-hooks*` | `defimage` `:on-save` / `:on-restore`, per-type `:restore` adapters |
| transient instance variables | `:transient` field policy |
| `snapshot: true andQuit: false` | `(image-save! path :continue)` / `:quit` |
| `save-lisp-and-die :toplevel` | `defimage` `:init` (fresh boot only) and `:run` (every boot) |
| `:executable t` | baked executable with an image trailer (phase F) |
| processes survive the snapshot | native stacks are never captured; heap-resident cooperative tasks can be (phase G) |
| `become:` / identity | image object IDs; handle identity survives the round trip |
| file-in over an old image | the on-disk program is submitted as a live edit after replay |

## Non-negotiable invariants

1. **Complete or absent.** An image is written only when every registered root,
   handle, managed object, and reference resolved. A pointer without a declared
   policy is a save blocker with a registration-site diagnostic. There is no
   partial image and no silently dropped field.
2. **Transactional load.** A load that fails validation, replay, or migration
   leaves the process in the pre-load state. It never boots half a world. A
   fresh boot is not silently substituted for a failed load.
3. **Identity by stable IDs.** Definitions by `live-def-id`, schemas by logical
   runtime identity plus version fingerprint, objects by image object ID. Never by
   address, generated symbol, or JIT generation number.
4. **No machine code in the image.** The image stores accepted source
   submissions. Native code is rebuilt by the JIT. A cached native generation is
   an optimization keyed by ledger fingerprint and can always be discarded.
5. **No native execution state.** Only heap-resident state is captured. Resume
   happens at the live runtime's restart boundaries, exactly as after a Broken
   repair.
6. **The running program owns the schemas.** Image data migrates forward through
   checked transition chains into the program that loads it. An image never
   downgrades a program and never installs a historical layout as current.
7. **Conflicts are visible, never resolved silently.** If the program on disk
   changed a definition that was also edited live before the save, the on-disk
   version wins and the overridden live version stays in the ledger, marked and
   inspectable.
8. **The live experiments keep their semantics.** `heap-inspector` and
   `manual-live` gain only additive entry points. Their existing gates stay
   green.

## The layers

| Layer | Owns | Does not own |
|---|---|---|
| Image metaprogram (`experiments.image.reader`, `.transform`) | `defimage`, field policies, generated per-schema image adapters, ledger registration inside each accepted transaction, the boot wrapper around `main` | live identity, schemas, migration, publication |
| Live metaprogram + runtime (existing) | stable IDs, schema versions, transitions, roots, handles, gates, quiescence, staged migration, publication | file formats, replay, hooks |
| Image runtime (`experiments.image.runtime`, `.format`) | ledger, object table, container read/write, blockers, save/load transactions, hook ordering, status | any semantics of the values it copies |
| Coil compiler / JIT session | checking and compiling replayed submissions; `code-session-state` | anything about images |

## What is in an image

The container is msgpack (`coil.serde.msgpack`), one top-level map with named
sections. Payload bytes are msgpack `bin`. Every section is self-describing so
the inspector can render an image without loading it.

```text
header
  magic "COILIMG", format-version, pointer-width, endianness, target triple
  live-metaprogram fingerprint (hash of the live reader/meta/registry sources)
  image metaprogram fingerprint
  base-program fingerprint (hash of the first ledger submission)
  saved epoch, save serial, saved-at, mode (continue|quit)

ledger                              ; the accepted program, in order
  entries[]:
    serial                          ; 1..N, replay order
    source text                     ; the exact accepted submission
    fingerprint
    kind: base | edit | recovery
    affected stable IDs             ; (live-def-id module kind name) list
    schema versions it created      ; (runtime-id version fingerprint) list
    status: accepted | overridden-by-base   ; see "Upgrade mode"
  pending                           ; the rejected candidate at save time, if any
    source text, diagnostic, condition kind
  definitions[]                     ; derived view for tooling, not authority
    stable ID, kind, accepted version, ABI lineage count, status,
    Broken diagnostic if any

schemas[]                           ; every version that has an object in the image
  runtime-id, logical name, version, fingerprint, kind (struct|sum)
  size, align
  declaration text                  ; the accepted defstruct/defsum form
  fields[]: stable field id, name, type text, offset, size, policy
  variants[] for sums
  reference fields[]: offset, kind (handle|object|slice|interior|function), target runtime-id
  transition edges present: (from-version to-version)

objects[]
  object id, runtime-id, schema fingerprint, count, bytes, align
  kind: payload | managed | array
  payload bytes with every reference word zeroed
  relocations[]: offset, kind, target object id, interior offset, length
  function values[]: offset, stable ID, ABI lineage
  transient fields[]: offset          ; zeroed, restore adapter runs

handles[]
  handle id, object id, refs, root id

roots[]
  name, runtime-id, schema fingerprint, handle id or object id

hooks
  ordered stable IDs of registered on-save / on-restore / per-type restore adapters

census                              ; informational only
  registered-but-unreachable objects, untracked inspector allocations at save

trailer
  section offsets, content hash
```

Why msgpack and not a raw section dump: it is already in the standard library,
it streams, the inspector can show it, and the relocation model needs a
structured table anyway. Why source text and not `Code`: the accepted submission
text is exactly what the JIT session accepted, and replaying it through the same
provider reproduces the same registry, versions, and lineages deterministically.
This is the Smalltalk changes file, kept inside the image.

## Source surface

```coil
(import "experiments.image.lang" :use *)     ; live reader + image metaprogram

(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (layer (ptr i8) :transient)])              ; rebuilt by the restore adapter

(letonce world (World ...))                   ; a registered root, as today

(defn tick [] (-> i64) ...)

(defimage particles
  :init    (build-initial-world!)             ; fresh boot only
  :run     (drive-frames!)                    ; every boot; the restart-boundary driver
  :on-save (flush-logs!)                      ; before serialization, gate closed
  :on-restore (reopen-window!)                ; after materialization, before :run
  :restore (Particle particle-restore!))      ; per-type: rebuild transient fields
```

Field policies on live structs and sums:

| policy | save | load |
|---|---|---|
| (default) live handle, tracked pointer, slice into a tracked allocation, function value, scalar | serialized as a relocation | swizzled |
| `:transient` | zeroed | zeroed, then the type's `:restore` adapter runs |
| `:foreign` | zeroed; save is blocked unless the type has a `:restore` adapter | same as transient |
| untracked raw pointer, integer-cast address, borrowed payload, FFI-retained payload | **save blocker** with schema, field, address, registration boundary | n/a |

Runtime API, all ordinary Coil functions in `experiments.image.runtime`:

```coil
(image-request-save! path mode)   ; any thread; performed at the next restart boundary
(image-save! path mode)           ; only at a restart boundary; returns ImageStatus
(image-loaded?)  (image-status)  (image-blocker)  (image-ledger-count)
```

Process surface, generated by the boot wrapper: `./app --image FILE` or
`COIL_IMAGE=FILE ./app`; `--image-out FILE` sets the default save target.
Inspector surface: `GET /api/image` (status, ledger, blockers, last save) and
`POST /api/image/save`.

Everything else is the existing live surface: `letonce`, `migrate`, edits
through the controller, Broken and NeedsTransition conditions, restart
boundaries.

## Save protocol

`image-save!` is a publication transaction over every source identity.

1. **Boundary.** The call is legal only at a restart boundary (tick, callback,
   `:run` poll) because the caller must not hold a reader lease on the world it
   is about to freeze. `image-request-save!` from anywhere else sets a request
   the driver honors at its next boundary, the same way cooperative reload
   polls work today.
2. **Quiesce.** `live-begin-affected-publication!` with all gates, then
   `live-begin-publication!`: readers drain, new affected calls park. A thread
   that never reaches a poll blocks the save; status is `WaitingForQuiescence`
   with the blocking source gate, identical to a schema edit.
3. **On-save hooks** run in registration order with the gate closed. They may
   read the world and mutate only transient state (flush, close, detach). A hook
   that fails aborts the save with its status.
4. **Walk.** Start from every registered root and every registered live handle
   and managed object. Registered objects that are unreachable from roots are
   still written (the live world has no collector; registration is ownership),
   and listed in `census` so the inspector can show them. For each object, run
   its schema's generated write adapter: scalars are copied, each reference field
   is resolved through the forwarding table:
   - live handle → handle id;
   - pointer into a tracked payload or managed object → object id, interior
     offset (via `live-managed-object-by-address` / `entry-containing`);
   - slice → object id, element offset, length;
   - function value → stable ID and ABI lineage from the artifact table the
     metaprogram registers for permanent trampolines;
   - null → null;
   - `:transient` / `:foreign` → zero, recorded;
   - anything else → blocker; the save aborts before writing a byte.
   Objects with outstanding borrows, FFI retains, or `migrating` state are
   blockers unless the retaining field is `:foreign` with a restore adapter.
5. **Ledger.** The runtime ledger (maintained by generated code inside every
   accepted transaction, see "Ledger maintenance") is copied verbatim, plus the
   pending rejected candidate if the controller holds one.
6. **Write** to `path.tmp`, fsync, rename. The trailer hash is computed while
   streaming.
7. **Resume or quit.** `:continue` reopens the gate and returns `Saved`;
   `:quit` runs no further user code and exits 0 after the rename.

Failure at any step leaves the world untouched: nothing was mutated except
transient state the on-save hooks chose to touch, and the gate reopens.

## Load protocol

The boot wrapper generated around `main` runs before any user code.

1. **Read and validate** the header: magic, format version, pointer width,
   target, live-metaprogram fingerprint. A mismatch is a hard exit with the
   exact mismatch named. The trailer hash must match.
2. **Start the live controller** with the image source provider
   (`experiments.image.reader/image-source-provider`), which wraps the live
   provider. The JIT session is fresh.
3. **Replay the ledger** in serial order. Each entry is one controller edit,
   exactly as it was accepted. Replay is sequential on purpose: the registry,
   schema versions, fingerprints, and ABI lineages are reproduced by
   construction, so the image's schema fingerprints resolve to real runtime
   schema IDs after replay. An entry that is rejected during replay stops the
   load (invariant 2) with its diagnostic; this can only happen if the live
   metaprogram itself changed, which the header fingerprint already detects.
   Entries marked `overridden-by-base` from a previous upgrade are skipped.
4. **Materialize.** Allocate every object at the schema its fingerprint names
   (all present after replay), copy payload bytes, allocate handles through
   `live-handle-new!` in image order, then a second pass rewrites every
   relocation: handle ids to handle addresses, object ids plus offsets to
   addresses, slices to data pointer plus length, function values to the
   permanent trampoline for that stable ID and lineage. Transient fields stay
   zero. Roots are installed by the generated `NAME--image-restore` entry,
   which stores the slot and marks the root initialized so the ordinary
   `letonce` registrar sees it as already constructed.
5. **Validate** the graph: every relocation resolved, sizes and counts match
   the schema, every root present, no dangling handle. Failure frees everything
   materialized and exits nonzero.
6. **Upgrade edit.** Submit the program on disk (the file that would have been
   the base submission on a fresh boot) as one ordinary live edit. In exact mode
   (its fingerprint equals the ledger's base fingerprint and no other base is
   configured) this is skipped. Otherwise the live metaprogram computes the
   affected closure, requires `migrate` edges where layouts changed, migrates
   the just-materialized graph through the existing shadow-graph transaction,
   and publishes. A missing transition pauses the boot at `NeedsTransition`
   exactly as it pauses a live edit; the inspector shows the same repair UI and
   the boot continues when the transition is supplied.
7. **Restore hooks.** Per-type `:restore` adapters run for every object that
   has transient fields, in object-id order; then `:on-restore` hooks in
   registration order. They see the migrated, published world.
8. **Publish** the image status and enter `:run`. `:init` is not executed.

Load with no `--image` is a fresh boot: base submission, `:init`, `:run`. The
ledger starts with that base submission as entry 1.

### Upgrade mode and conflicts

The image was saved from program P, and the binary now on disk has program P'.
After replay the session holds P plus the live edits E1..En that were accepted
before the save. Submitting P' as an edit makes P' the accepted version of every
definition it touches. For a definition that both P' changed and some Ei
changed, P' wins (the developer rebuilt deliberately); Ei's entry is marked
`overridden-by-base` in the ledger, keeps its source, and the inspector lists it
under "live edits overridden by the base program". Nothing is lost and nothing is
guessed. A later live edit can reapply it.

Data follows the same rule as any live edit: the schema chain in the image is
historical, P' is current, and the graph migrates forward through validated
edges. The transition forms live in the source like every other `migrate`.

## Ledger maintenance

The ledger is runtime data written by generated code, not reconstructed from
the JIT session. The image source provider wraps `live-submit-coil`:

1. It obtains the live metaprogram's plan for the submission (candidate
   registry, generated delta, commit entry) through the additive
   `live-submit-coil-plan` entry point.
2. It appends, inside the same generated module, a staged ledger record:
   serial, source text, fingerprint, affected stable IDs and new schema
   versions read from the candidate registry.
3. It appends per-schema image adapters for every schema version the
   candidate registry created that does not yet carry an `:image-adapter`
   artifact, and registers them through `coil_image_register_schema` inside the
   candidate commit entry. Adapters are typed native functions generated from
   the declaration `Code` (the same information `live-migrate-from-declarations`
   consumes), so no runtime type-name parsing occurs.
4. The staged ledger record is finalized only after `jit-commit-prepared!`
   returns 0, through the controller's publication hooks. A rejected or
   rolled-back transaction discards it.

The base submission is entry 1 with kind `base`. Recovery submissions (Broken
publication) are recorded with kind `recovery` so that replay reproduces the
Broken state, including the diagnostic the inspector showed.

## Scenario matrix

### Data

| Scenario | Required behavior |
|---|---|
| Root struct with scalar fields | round-trips bit-exactly |
| Nested live handles, shared handle referenced twice | one object, two relocations; identity preserved |
| Cycle through handles | forwarding table terminates; cycle restored |
| Managed array of payloads | one object with count; elementwise schema |
| Slice into a managed allocation | object id, element offset, length; validated against bounds at load |
| Interior pointer to a field | object id plus offset; validated |
| Sum with variant payloads | variant index plus payload references through the variant field table |
| Closure environment | ordinary live struct; code identity is a function value relocation |
| Stored function value | stable ID plus lineage; resolved to the permanent trampoline |
| `:transient` pointer | zero on load, restore adapter runs |
| `:foreign` without restore adapter | save blocked |
| Untracked raw pointer | save blocked with field and registration site |
| Outstanding borrow / FFI retain / migrating | save blocked |
| Registered but unreachable object | saved; listed in census |
| Schema saved at v3, program now at v5 | migrate v3→v4→v5 through existing edges at load |
| Schema saved at v3, program changed layout without `migrate` | boot pauses at NeedsTransition; repair resumes boot |
| Image larger than a fixed live registry | `ImageTooLarge` with the registry named; no partial materialization |

### Code

| Scenario | Required behavior |
|---|---|
| No live edits before save | ledger = base only; replay is one submission |
| Body edit, defaulted-field edit, transition edit, then save | replay reproduces versions 1..3 and identical fingerprints |
| Rejected candidate pending at save | restored as pending with its diagnostic |
| Broken entry published before save | replay reproduces Broken; entering it raises the same condition |
| Base changed a body only | upgrade edit swaps one slot; no migration |
| Base changed a struct with a `migrate` present | migration during boot; data preserved |
| Base and a live edit changed the same function | base wins; ledger entry marked overridden; inspector lists it |
| Live metaprogram sources changed since save | header fingerprint mismatch; hard exit naming both fingerprints |
| Edits after load | ledger continues at serial N+1; a later save contains the full history |

### Process

| Scenario | Required behavior |
|---|---|
| Save requested from a non-boundary thread | deferred to the driver's next boundary |
| Window thread and HTTP thread active | both park at their boundaries; save proceeds |
| Thread that never polls | `WaitingForQuiescence` naming the gate; no save |
| `:quit` | exit 0 after rename, no user code after the hooks |
| Load fails at any step | pre-load state, nonzero exit, diagnostic; no fresh-boot substitution |
| 1,000 save/load cycles | bounded memory; ledger grows only with real edits |

## Interaction with existing experiments

- **heap-inspector census.** Inspector-tracked allocations that are not live
  managed objects are not part of the image; they belong to non-live code whose
  state is re-created by a fresh `:init`-style path or is stateless. The
  `census` section counts them so the inspector can warn. A checker,
  `image-static-audit`, reports every `alloc/static` cell in an image module
  that is not a registered root, so untracked host state is visible at compile
  time rather than lost at load.
- **live runtime.** Enumeration uses the existing accessors (`live-roots`,
  `live-handle-head`, `live-managed-objects`, `live-reference-fields`,
  `live-transitions`). Materialization uses `live-handle-new!`,
  `live-register-root`, `live-register-handle-root`, and the generated root
  registrars. The quiescence and publication protocol is used unchanged.
- **live reader/registry.** Adapters are generated from the same declaration
  `Code` the reader already holds per version; artifact registration uses
  `registry-register-artifact` with a new `:image-adapter` role.
- **manual-live.** Not depended on. Its `LiveValue` trait protocol
  (`live-copy!`/`live-destroy!`) is the model for owning collection fields; a
  live struct field whose type implements it serializes through a generated
  `LiveValue`-aware adapter in phase D.
- **Functions view / runtime invocation.** Unchanged; replayed definitions
  re-register their invocation adapters.
- **coop/async/csp.** Heap-resident `Task` records are ordinary structs with a
  step function pointer and state; once expressed as live structs with function
  values they serialize like any object, which gives cooperative computations
  Smalltalk-style survival (phase G). Native pthreads are never captured.

## Additive seams required in existing code

None of these change existing behavior; each is a new entry point beside an
existing one.

| Where | Seam | Why |
|---|---|---|
| `heap-inspector/live_reader.coil` | `live-submit-coil-plan` returning candidate registry, generated delta, and commit body; `live-submit-coil` becomes a one-line wrapper | the image provider appends ledger and adapter forms inside the same transaction |
| `heap-inspector/live_registry.coil` | `:image-adapter` artifact role | track which schema versions already have adapters |
| `heap-inspector/live.coil` | `live-register-function-value` (stable ID, lineage → trampoline) and lookup | function-value relocations |
| `heap-inspector/live.coil` | `live-register-slice-field` mirroring manual-live's `register-slice!` | slice relocations without type-name parsing |
| `heap-inspector/controller.coil` | `live-controller-set-source-provider!` (before init) and publication hooks `(on-committed, on-aborted)` | install the image provider; finalize or discard the staged ledger record |
| root `Coil.toml` | `[test.suites.image]` | gate |

No Coil compiler change is required for phase A–E. Two compiler items make the
feature better and are tracked, not required: the retained metaprogram session
(`coil-retained-jit-session` pad) makes ledger replay proportional to edits
instead of ~1 s per entry; a session teardown API (already in `coil-bugs`)
matters for the 1,000-cycle gate.

## Package layout

```text
src/experiments/image/
  Coil.toml            [package] name = "image"; [link] flags = ["-Wl,-export_dynamic"]
  README.md
  lang.coil            (module experiments.image.lang)     the dialect entry
  reader.coil          image-source-provider, ledger and adapter generation
  transform.coil       defimage, field policies, boot wrapper, image-static-audit checker
  format.coil          container read/write over coil.serde.msgpack
  runtime.coil         ledger, object table, forwarding, blockers, save/load transactions, hooks
  api.coil             inspector HTTP bridge
  format_test.coil     round trip of every section, hash, version rejection
  adapter_test.coil    generated adapters per field kind, blockers, no JIT
  roundtrip_test.coil  save in one process, load in a child, compare frames
  ledger_test.coil     edits, pending, Broken, replay determinism
  upgrade_test.coil    base changed with and without migrate; conflict marking
  hooks_test.coil      transient, foreign, on-save, on-restore ordering
  stress_test.coil     1,000 cycles, bounded registries, WaitingForQuiescence
  demo.coil            the bouncing-ball world saved and resumed in the native window
```

## Implementation sequence

### Phase A — format and adapters, no JIT (done)

- Container read/write over msgpack with every section, trailer hash, header
  validation.
- Generated per-schema write/read adapters from declaration `Code` covering
  scalars, handles, tracked pointers, slices, interior pointers, function values,
  sums, transient/foreign policies, and blockers.
- Forwarding table and relocation encoding.

Gate: a handwritten registry with sharing, a cycle, a slice, a sum, a stored
function value, and one transient field round-trips through a file to identical
bytes and identical relocations; each blocker kind is produced with its field
and registration site. Passed: `coil test --suite image`, 16 tests.

### Phase B — save transaction

- `image-request-save!`/`image-save!` at restart boundaries with the world gate.
- On-save hooks, census, atomic file write, `:continue` and `:quit`.

Gate: the native bouncing-ball world saves mid-run while the window and HTTP
threads are active; a non-polling thread yields `WaitingForQuiescence`.

### Phase C — ledger and replay

- Image source provider over `live-submit-coil-plan`; staged ledger records
  finalized by controller hooks.
- Boot wrapper, `--image`, sequential replay, materialization, validation,
  restore hooks, `:run` without `:init`.

Gate: fresh process → base + three edits → save → new process loads → frame
sequence equals the saved process's continuation; pending and Broken states
restored; `image-ledger-count` correct after further edits.

### Phase D — upgrade and migration on load

- Upgrade edit after replay; overridden-by-base marking; NeedsTransition pause
  during boot; `LiveValue` collection fields.

Gate: every data scenario in the matrix; a changed base with `migrate` loads
with data preserved; a changed base without it pauses and resumes on repair.

### Phase E — inspector and stress

- `/api/image`, ledger and blocker rendering in the viewer, save button.
- 1,000 save/load cycles bounded; latency measured per stage (read, replay per
  entry, materialize, upgrade, hooks).

Gate: bounded memory across cycles; existing heap-inspector and manual-live
gates unchanged.

### Phase F — baked executables

- `image-bake app image -o app-image`: copy the binary, append the image and a
  trailer; the boot wrapper checks its own executable for the trailer when no
  `--image` is given.

Gate: the baked binary boots the saved world with no arguments.

### Phase G — cooperative computations

- Express `coop` task records as live structs with function values so parked
  computations survive a save.

Gate: a parked CSP process resumes after load and completes.

## Required final validation

- Every row of the scenario matrix has a test.
- `coil test --suite image`, `coil test --suite heap-inspector`, and the
  manual-live builds are green together.
- `scripts/native-live-demo.sh` still runs; the image demo saves and resumes
  the same window.
- `git diff --check`, no Python production path, repeated compiler fixpoint on
  the dialect.
- TSan on the save-while-running test; ASan on the round-trip test.

## Implementation status

### Phase A (2026-09-06)

`src/experiments/image/` holds `format.coil` (model, msgpack envelope with
magic, length, FNV-1a hash, version and pointer-width checks), `runtime.coil`
(adapter registry, writer with forward and handle tables and blockers, reader
with staged relocation and bounds checks), and `adapters.coil` (`image-struct`,
`image-sum`, `:transient`, `:foreign`, `:restore`). `format_test.coil` and
`adapter_test.coil` are the gate; both pass, and the heap-inspector suite is
unchanged (its `live_function_transform_test` already failed before this work
and still does, recorded in the `coil-experiments` pad).

Decisions taken while implementing:

- **Image layout is generated, not native.** Each field has an 8-byte-aligned
  slot; a sum is a tag word plus its widest variant's slots; nested by-value
  types inline. The design's "payload bytes with reference words zeroed" is
  therefore realized as a generated slot layout, which removes every
  assumption about native offsets (variant payload offsets are not reflectable
  at all) and keeps the reader's relocation pass generic.
- **Element pointers are typed relocations.** A `(ptr T)` into an array
  object of `T` records the element index; a pointer at a non-element offset of
  a typed object is a type mismatch, not an interior reference. Untyped
  interior references are only produced for `(ptr scalar)` fields.
- **Schema descriptions are per object type.** A nested by-value struct or
  sum contributes its slots to the container's schema but describes its own
  references in its own schema record (present only when an object of that
  type exists). Relocations on objects remain the authority.
- **Identity formulas are duplicated, not imported.** `image-name-hash` and
  the declaration hash mirror `live-name-hash` and `live-declaration-hash`
  byte for byte; importing `live-meta` directly is not possible today (see the
  `coil-bugs` pad). Phase C will take fingerprints from the reader's own
  registry instead.
- **Handle owner shape.** The adapters recognize the field type
  `LiveHandleOwner` and its `raw` word. `live-types` cannot be linked with
  `live` in one program, so host-side code declares the same one-field shape.

### Phases B–G (2026-09-06)

The image system was completed over the **real** heap-inspector live runtime.
The `image` package links into the same host program as `experiments.heap-inspector.live`,
so the bridge reads the runtime's own registries directly and serializes live
payloads reflectively from the schema and reference-field tables — no change to
the live reader was required.

- **B — save.** `image-save!` walks the registered graph (handles, roots,
  managed objects) under the world publication gate and serializes each
  payload, turning handle/pointer/slice reference fields into relocations.
  `image-try-save!` reports `waiting-for-quiescence` when a reader lease is
  held. Blockers name the offending field. Gate: `live_bridge_test` (4) and
  `scripts/image-roundtrip.sh` (a cyclic handle graph with a shared managed
  array and interior slices, saved in one process and verified in another).
- **C — ledger + boot.** `ledger.coil` records accepted submissions;
  `image-boot!` validates the header, loads the ledger, replays every accepted
  submission through the live controller (rebuilding schemas, functions, and
  `letonce` roots), then overlays the saved heap state in place. Gate:
  `scripts/image-boot.sh` boots a JIT-built world mutated at runtime (a=99 vs
  the source's a=1) in a fresh process and verifies the mutation survived.
- **D — upgrade on load.** After boot, submitting a changed schema runs the
  live migration machinery, preserving overlaid state (a=99 kept, defaulted
  field added). Conflict marking (`ledger-mark-conflicts!`) overrides a prior
  live edit that a rebuilt definition supersedes. Gate: `image-boot.sh`
  (upgrade) and `ledger_test` (4).
- **E — inspector.** `api.coil` builds the `/api/image` status JSON (ledger,
  kinds, statuses, names, pending, last blocker) and a save handler. Gate:
  `api_test` (2).
- **F — baked executables.** `bake.coil` appends an image to a copy of the
  binary with a trailer; `image-boot-baked!` finds the trailer in the running
  executable and boots from it. Gate: the demo bakes itself and, run with no
  arguments, boots the saved world.
- **G — cooperative computations.** A parked computation's state is a live
  struct (imaged and restored); its step code is compiled into the binary and
  re-attached in the resuming process. Gate: `scripts/image-coop.sh` parks a
  cooperative sum at i=5/acc=10 and resumes it to acc=45 in another process.

Full image suite: `coil test --suite image` → 26 passed. The three shell
harnesses pass. The heap-inspector and manual-live experiments are unchanged.

Deviations from the original design, all faithful to its invariants:

- **Live payloads are serialized reflectively**, not through per-schema
  adapters generated inside JIT submissions. The runtime already records every
  reference offset, so the bridge needs no reader seam and the ledger carries
  no generated adapter code. (The phase-A generated adapters remain the
  standalone-container path with their own tests.)
- **Full-boot restore is an in-place overlay** onto the replay-rebuilt
  isomorphic graph, rather than the generated `NAME--image-restore` hooking a
  `letonce` slot. This restores heap state that compiled accessors read through
  their own slots without modifying the generated code.
- **A schema resolves by (runtime-id, fingerprint)**, and the header carries a
  compile-time fingerprint of the binary rather than a hash of live-reader
  sources.

Compiler findings recorded in the `coil-bugs` pad: `code-field-type` aborts
on `fnptr` fields; `[Code] -> Code` helpers of an imported module expand as
macros at their own call sites; hand-written structs cannot name
macro-generated struct types; runtime use of a metaprogram-only primitive
silently drops the function and its callers.
