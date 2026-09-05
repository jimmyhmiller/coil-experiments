# coil-experiments

Languages, applications, and research dialects built in [Coil](https://github.com/jimmyhmiller/coil).

Nothing here is part of the Coil language or its standard library. This is the
place for the fun stuff: things that exercise the compiler hard, demonstrate
what the metaprogramming model can do, or exist because they were interesting.
It all used to live in the Coil repo, where it kept getting mistaken for the
API surface.

## What's here

### `src/apps/scheme/` — an R5RS Scheme dialect
About 17,000 lines. One import (`(import "experiments.scheme.lang" :use *)`) and you write
real Scheme in a `.scm` or `.coil` file: proper tail calls, `call/cc`,
`define-syntax` with `syntax-rules`, bignums, ports, a precise GC. The dialect
is a `:phase before-expand` whole-program transform — the compiler has no
Scheme in it. See [`docs/R5RS_STATUS.md`](docs/R5RS_STATUS.md) for conformance.

### `src/dialects/brainfuck/` — a reader metaprogram
A reader provider that compiles raw `.bf` bytes to a complete Coil module at
compile time — direct tape operations and native loops, no interpreter.

```sh
coil run tests/brainfuck/hello.bf --use experiments.brainfuck.lang
coil run experiments.brainfuck.lang tests/brainfuck/hello.bf   # print the emitted Coil
```

### `src/dialects/c/` — a C compiler written in Coil
`cc.coil` lexes, preprocesses, parses, type-checks, and lowers C11 with nothing
but Coil code: no Clang, no JSON, no external tool between the source text and
the emitted Coil. It reads the system's own headers, compiles a whole program at
once into a single Coil module — no object files and no linker of its own — and
is ported from [chibicc](https://github.com/rui314/chibicc). The pinned gate
builds Doom Generic as 81 translation units and verifies its exact 1,000-frame
framebuffer hash; `--play` builds the windowed game with sound. See
[`src/dialects/c/README.md`](src/dialects/c/README.md) and
[`MULTI-UNIT.md`](src/dialects/c/MULTI-UNIT.md).

```sh
python3 scripts/c-doom-native.py          # Doom, 81 translation units
python3 scripts/c-doom-native.py --play   # the windowed game, with sound
python3 scripts/c-doom-native.py --play --heap-inspector  # game + live heap viewer
```

The heap-inspected build serves the viewer from the Doom process at
<http://127.0.0.1:7391/> and opens it automatically. Pass
`--no-open-inspector` to leave the browser closed. If port 7391 is occupied, the
launcher selects the next available port; `--inspector-port N` changes the
preferred starting port.

### `src/dialects/rust-like/` — a round-trippable Rust-like reader
A reader metaprogram and converter for writing Coil with Rust-like declarations,
blocks, expressions, traits, imports, and control flow. A lossless structural
Rust-like notation represents every Coil form without embedding native Coil,
while dedicated surface syntax makes common forms pleasant to write. The
integration gate converts, builds, and runs a full copy
of the Coil compiler through one `--use experiments.rust-like.lang`. See
[`src/dialects/rust-like/README.md`](src/dialects/rust-like/README.md).

### `src/apps/` — applications
- `emacs/` — GNU Emacs compiled as one whole program by the Coil C reader
- `chip8/` — CHIP-8 emulator with an AppKit GUI
- `clox/` — the Crafting Interpreters bytecode VM, at rough parity with `-O2` C
- `invaders/` — an 8080 emulator running Space Invaders
- `web/` — WebAssembly: a counter and a TodoMVC, with a JS/DOM bridge
- `mini-scheme/` — a metacircular Scheme evaluator with no pointers, no
  allocation, and no rooting in its source; a transform inserts the whole GC

### `src/experiments/` — research
- `gc-dialect/` — explicit-root garbage collection as a dialect
- `transparent-gc/` — the follow-on transform that inserts the roots
- `httptap/` — HTTP interception as a whole-program transform, three sinks
- `coop/` — shared FIFO scheduler for lightweight resumable computations
- `async/` — generated activation records; `await` parks the current computation
- `csp/` — Go-style processes with parking, bounded channels, and backpressure
- `dataflow/` — Oz-style logic variables that suspend and wake dataflow threads

The three concurrency dialects include runnable business-shaped examples and a
design/tradeoff discussion in
[`docs/CONCURRENCY_METAPROGRAMS.md`](docs/CONCURRENCY_METAPROGRAMS.md).

### `tests/` and `scripts/`
`tests/staged-meta/` holds the staged-metacompilation bridge that computes
through the Scheme phase runtime at expansion time. `tests/scheme/` is the
conformance corpus: a differential harness against Chez,
Guile, and Chibi (`tests/scheme/run.py`), the dialect suite, MAL, a Lox
interpreter written in Scheme, and benchmarks. The `scripts/scheme-*.py` drive
them.

```sh
python3 scripts/scheme-progress.py --compiler "$(command -v coil)"
python3 tests/scheme/run.py --list
scripts/rust-like-test.sh
```

## Building

Everything here consumes an installed Coil toolchain — there is no compiler in
this repo. Pass `--compiler` to the scripts, or put `coil` on your `PATH`.

## Layout

This is a Coil **workspace** named `experiments`. Every directory under
`src/apps`, `src/dialects` and `src/experiments` is a member package with its own
`Coil.toml`, and its modules are `experiments.<package>.<name>` — the Scheme
evaluator is `experiments.scheme.eval`, the CHIP-8 CPU is `experiments.chip8.lang`.
Members compile together and refer to each other directly; nothing declares a
dependency on anything.

```sh
coil test                       # the deftest suites (191 Scheme tests)
coil test --suite mal           # opt-in: slow, several currently red
coil check                      # typecheck every member that is a program
python3 scripts/experiments.py --compiler "$(command -v coil)"
```

That last one is the corpus runner: the demos here are programs, not `deftest`s,
so their contract is "runs, prints this, exits N". `tests/experiments.txt` lists
them and `tests/reference/` holds blessed stdout and exit status, so a silent
change in what a demo prints fails rather than passing quietly. Re-freeze with
`--bless` after an intentional change.

## Known broken

- `src/apps/mini-scheme/scheme.coil` does not compile: the GC transform leaves
  `Val` unresolved and the build dies with 20 errors. It predates the workspace
  conversion. It is commented out of `tests/experiments.txt` rather than blessed
  at exit 1, which would have reported health it does not have.
- Several `--suite mal` stages fail, some by SIGABRT in the compiler.
