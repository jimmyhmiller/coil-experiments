# coil-experiments

Languages, applications, and research dialects built in [Coil](https://github.com/jimmyhmiller/coil).

Nothing here is part of the Coil language or its standard library. This is the
place for the fun stuff: things that exercise the compiler hard, demonstrate
what the metaprogramming model can do, or exist because they were interesting.
It all used to live in the Coil repo, where it kept getting mistaken for the
API surface.

## What's here

### `src/apps/scheme/` — an R5RS Scheme dialect
About 17,000 lines. One import (`(import "coil.scheme" :use *)`) and you write
real Scheme in a `.scm` or `.coil` file: proper tail calls, `call/cc`,
`define-syntax` with `syntax-rules`, bignums, ports, a precise GC. The dialect
is a `:phase before-expand` whole-program transform — the compiler has no
Scheme in it. See [`docs/R5RS_STATUS.md`](docs/R5RS_STATUS.md) for conformance.

### `src/dialects/brainfuck/` — a reader metaprogram
A reader provider that compiles raw `.bf` bytes to a complete Coil module at
compile time — direct tape operations and native loops, no interpreter.

```sh
coil run tests/brainfuck/hello.bf --use brainfuck   # Hello World!
coil run brainfuck tests/brainfuck/hello.bf         # print the emitted Coil
```

### `src/apps/` — applications
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

### `tests/` and `scripts/`
`tests/scheme/` is the conformance corpus: a differential harness against Chez,
Guile, and Chibi (`tests/scheme/run.py`), the dialect suite, MAL, a Lox
interpreter written in Scheme, and benchmarks. The `scripts/scheme-*.py` drive
them.

```sh
python3 scripts/scheme-progress.py --compiler "$(command -v coil)"
python3 tests/scheme/run.py --list
```

## Building

Everything here consumes an installed Coil toolchain — there is no compiler in
this repo. Pass `--compiler` to the scripts, or put `coil` on your `PATH`.

## Known debt

`src/apps/scheme` still declares the `coil.scheme.*` namespaces, which belong to
Coil's standard library, not to this repo. It cannot be renamed yet: Coil's
loader triggers the dialect's ASCII identifier case-folding by scanning for a
literal `(import "coil.scheme" …)` form (`src/compiler/loader.coil`). Renaming
these namespaces needs that hook generalized upstream first.
