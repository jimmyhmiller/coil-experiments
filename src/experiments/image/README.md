# Coil image metaprogram

First-class Smalltalk/Lisp-style images for live Coil programs, built over the
`heap-inspector` native live runtime. Save the running world — its accepted
program and its live object graph — to one file; load it in another process and
carry on. The design is `docs/IMAGE_METAPROGRAM.md`; this package is the
implementation.

## What works

All phases A–G are implemented and gated. The image system operates on the
**real** live runtime: real `LiveHandle`/`LiveRoot`/schema registries, the real
world publication gate, the real JIT controller for code replay, and the real
migration machinery for upgrades. Live payloads are serialized reflectively from
the runtime's own schema and reference-field tables, so no change to the
3,900-line live reader was needed.

```sh
# unit tests (fast, forked per test)
coil test --suite image

# the cross-process gates (a real second process loads the image)
scripts/image-roundtrip.sh   # B/C: save a live handle graph, load+verify elsewhere
scripts/image-boot.sh        # C/D: replay code + overlay heap state, then migrate on load
scripts/image-coop.sh        # G:   park a cooperative computation, resume it elsewhere
```

| Phase | What | Gate |
|---|---|---|
| A | container format + generated adapters | `format_test`, `adapter_test` (16) |
| B | gated save of the live world; blockers; quiescence | `live_bridge_test` (4); `image-roundtrip.sh` |
| C | ledger of accepted submissions; replay + boot | `ledger_test` (4); `image-boot.sh` (boot) |
| D | upgrade-on-load migration; conflict marking | `image-boot.sh` (upgrade); `ledger_test` |
| E | inspector status JSON | `api_test` (2) |
| F | baked self-booting executables | `image-boot-demo bake` → run with no args |
| G | cooperative-computation capture and resume | `image-coop.sh` |

## Demos you can run

```sh
scripts/image-workspace.sh   # a counter + notes list: snapshot, boot in microseconds, bake to an exe
scripts/image-adventure.sh   # a text adventure whose whole world is a live object graph
```

The adventure is the fullest example: a dozen rooms cross-linked by exits (a
cyclic graph), items that live in rooms or your pack, and a player standing
somewhere holding things. Play it, `save FILE` mid-game, and a fresh process
boots that exact world in well under a millisecond:

```sh
coil build src/experiments/image/adventure.coil -o build/adventure
build/adventure new                         # play; type `save game.img` then `quit`
build/adventure boot game.img               # resume exactly where you left off
build/adventure bake build/adventure game.img game   # one self-booting file
./game                                       # the executable IS your saved game
```

## How it fits together

- **`format.coil`** — the `Image` container: header, ledger, pending candidate,
  schemas, objects with relocations, handles, roots, hooks, census; msgpack
  encoding with a validated envelope (magic, length, FNV-1a hash, version,
  pointer width). Damage of any kind is a specific `ImageFormatError`.
- **`live_bridge.coil`** — the bridge to the live runtime. Save walks the
  registered graph and serializes each payload's native bytes, turning every
  registered reference (handle, tracked pointer, slice) into a relocation.
  `bridge-materialize!` rebuilds the graph into fresh handles for a data reload;
  `bridge-restore-in-place!` overlays saved heap state onto an isomorphic graph
  after a code replay (full boot), preserving the generated accessors' view.
- **`ledger.coil`** — the accepted-submission ledger (the code half): record,
  container in/out, header validation, and conflict marking (a rebuilt
  definition overrides a prior live edit of the same name).
- **`image.coil`** — the front door: `image-save!` (under the publication
  gate), `image-try-save!` (non-blocking, reports `waiting-for-quiescence`),
  `image-load-data!` (schemas + graph, no code), `image-boot!` (replay the
  ledger through the controller, then overlay heap state), and
  `image-controller-edit!` (a ledger-recording edit).
- **`bake.coil`** — append an image to a copy of the binary with a trailer;
  `image-boot-baked!` finds the trailer in the running executable and boots.
- **`api.coil`** — the inspector status JSON (`image-status-json`,
  `image-save-json`) the viewer can serve at `/api/image`.
- **`runtime.coil`, `adapters.coil`** — the phase-A standalone container writer,
  reader, and `image-struct`/`image-sum` adapter generators, with their own
  tests. The live path reuses `format.coil` and the blocker vocabulary.
- **`image_boot.coil`** — the controller-backed half: `image-boot!`,
  `image-controller-edit!`, and the full baked boot. Only programs that restore
  code use this.
- **`jit_host.coil`** — that half packaged as a prebuilt static library behind a
  C ABI, so an app links the compiler instead of recompiling it.
- **`roundtrip.coil`, `boot_demo.coil`, `coop_demo.coil`, `workspace_demo.coil`,
  `adventure.coil`** — the demo programs driven by the shell harnesses.

## Design decisions worth knowing

- **The image is the live runtime's own graph.** Save reads `LiveHandle`/
  `LiveRoot`/`LiveManagedObject` and the schema/reference tables directly; load
  rebuilds real handles and roots. It is not a separate serializer bolted on.
- **Full boot = replay + in-place overlay.** Replaying the ledger through the
  controller rebuilds schemas, functions, and `letonce` roots with the base
  program's initial state; the image then overlays captured runtime state onto
  that isomorphic graph in place. This restores heap state that compiled
  accessors read through their own root slots, with no live-reader surgery.
- **Cooperative computations: data is imaged, code comes from the program.** A
  parked computation's state is a live struct (imaged and restored); its step
  function is compiled into the binary and re-attached in the resuming process.
  Raw function pointers are never stored — a fnptr reference field is rejected.
- **Identity by (runtime-id, fingerprint).** A schema always resolves by this
  pair, never by the schema index, which differs across processes.
- **Header fingerprints reject a mismatched binary.** A compile-time constant
  identifies this binary's live metaprogram and image format; a boot refuses an
  image from a different build.

## Build time

Nothing here should take tens of seconds to build. Two things made it slow, and
both are fixed.

**1. Don't compile the compiler into apps that don't JIT.** `image.coil` (save,
`image-load-data!`, diagnostics) and `bake.coil` are controller-free; the
controller-backed half lives in `image_boot.coil`. Importing the live controller
drags Coil's whole in-process compiler (`coil.jit`) into the binary, and at the
default `-O3` LLVM then optimizes all of it.

**2. When you do need the JIT, link it, don't recompile it.** `jit_host.coil`
wraps the controller-backed half behind a small C ABI and builds once into a
static archive. `boot_demo` links that archive and imports neither the
controller nor the live runtime.

```sh
coil build src/experiments/image/jit_host.coil --lib -o build/libcoilimage.a -O1
coil build src/experiments/image/boot_demo.coil -o build/image-boot-demo \
  --link-flag "$PWD/build/libcoilimage.a"
```

| build | before | after |
|---|---|---|
| `adventure` / `workspace_demo` / `coop_demo` / `roundtrip` | ~28 s | ~1.5 s |
| `coil test --suite image` (26 tests) | > 60 s | ~2.5 s |
| `boot_demo` (needs the JIT) | 37 s | **0.45 s** |
| the JIT host archive | — | 16.7 s, once |

`scripts/image-boot.sh` rebuilds the archive only when the image or
heap-inspector sources are newer than it.

Two caveats, both filed in the `coil-bugs` pad. `-O1` is the floor for anything
importing `coil.jit`: at `-O0` LLVM aborts on Coil's guaranteed `musttail`.
And linking a Coil archive into a Coil program warns about duplicate stdlib
`alloc-static` symbols (the linker picks one, which is the desired single
instance, and the save/boot/upgrade gates pass) — `-Wl,-force_load` turns those
warnings into errors, so don't use it here; ordinary transitive archive pulls
bring in the live runtime's object and its `coil_live_*` entry points, which
JIT-compiled code resolves through `dlsym` at runtime.

An application that links the archive must **not** also import
`experiments.heap-inspector.live`: the archive owns the live runtime's
registries, and a second import would create a disjoint set of cells. Everything
an app needs is exported through the C ABI in `jit_host.coil`.

## Compiler limits met while building this (recorded in the `coil-bugs` pad)

- A hand-written `defstruct` cannot name a struct produced by a macro.
- Importing `experiments.heap-inspector.live-meta` into an ordinary program
  makes its `[Code] -> Code` helpers expand as macros at their own call sites,
  so the adapters mirror the two hashing formulas they need.
- `code-field-type` on a `fnptr` field aborts the compiler.
- A runtime function that calls a metaprogram-only primitive is silently
  dropped along with its callers.
- `experiments.heap-inspector.live-types` and `.live` cannot be linked into one
  program (an extern collides with an export-c), so host-side code declares the
  one-field `LiveHandleOwner` shape locally.
