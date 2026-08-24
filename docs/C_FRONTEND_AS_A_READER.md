# What stops `coil run prog.c --use experiments.c.lang`

The C frontend in `src/dialects/c/` is a program with a `main`: it reads `.c`
files, writes a `.coil` file, and exits. The goal is for it to be a reader
metaprogram instead, the way `experiments.brainfuck.lang` is — `--use` it and the
C compiles and runs in one step, with no intermediate file.

This is what currently prevents that. Everything below was measured on
`coil` at `/Users/jimmyhmiller/.cargo/bin/coil`, macOS arm64, with a throwaway
reader provider (`(reader-provider "probe.reader" read-probe)`).

## Not blockers

Worth stating first, because they are the things one would expect to be problems
and are not:

- **Speed.** The environment a reader runs in executes ordinary Coil at roughly
  half the speed of an unoptimised native build: a 1,000,000-iteration integer
  loop took **6,503 µs** inside a reader versus **3,050 µs** in a `-O0` binary.
  The frontend is a large program, but it is not going to run at interpreter
  speed.
- **Collections and allocation.** `coil.alloc/malloc-allocator`,
  `coil.arraylist`, `coil.hashmap`, `coil.str` and its `StrBuf` all work
  unchanged. The frontend leans on all of them.
- **libc.** `extern` declarations resolve and call correctly from a reader.
  Verified with `strtod` (which `parse.coil` needs to round decimal float
  literals) and with `fopen`/`fread`/`fclose`.
- **`coil.os`.** `os/getpid`, `os/open`, `os/close` all work.
- **Reading files as such.** Not sandboxed at all — `fopen`/`fread` from a reader
  read a file off disk successfully. See blocker 1 for what actually fails.

## Blocker 1 — `coil.fs` is partly unusable from a reader

`#include` means opening arbitrary files while the compiler is running the
reader. `coil.fs` is the natural way to do that, and two of its entry points do
not work:

```lisp
(import "coil.fs" :as fs)
(match (fs/read-file (alloc/malloc-allocator) path) ...)
```

```text
error: in 'probe.reader.read-probe': call to undefined function 'coil.fs.read-file'
```

```lisp
(match (fs/write-file a "/dev/null" "x") ...)
```

```text
error: in 'coil.fs.write-file': unbound variable 'O_CREAT'
```

The second error is the informative one. `O_CREAT` is not a plain constant in
`coil.fs`; it comes out of `gen-open-flags`, which is built on `os-pick`, a macro
that chooses different numeric values for Linux and macOS. So the module's
macro-generated definitions are not being expanded when `coil.fs` is loaded for a
`:phase read` metaprogram, and `read-file` — which presumably folds through the
same machinery — comes out missing entirely rather than merely broken.

It is not the whole module. These are reachable from a reader and behave
correctly:

- `fs/file-open`, `fs/file-close`, `fs/file-fd`
- `fs/O_RDONLY`, `fs/FILE_MODE_DEFAULT`

So the fix is narrow: whatever expands `coil.fs`'s platform-conditional
definitions needs to run when the module is loaded into the reader's environment.
Once `fs/read-file` works, `#include` works.

## Blocker 2 — `code-read` will not take a string the reader computed

`emit.coil` builds its output as text, in a `str/StrBuf`, about 1,000 lines of
`put!` calls. The cheap way to make it drive a reader is to hand that text to
`primitive/code-read` and let the built-in reader parse it into `Code`. That is
what `code-read` is documented for: *"Intended for `:phase read` metaprograms that
delegate to the built-in reader."*

It does not accept a runtime string:

```lisp
(primitive/code-read (str/sb-str (load (mut b))) "")
```

```text
error: code-read: expects string Code and reader-config Code
```

It wants a string *`Code` node* — a literal known at expansion time — not a
`(slice u8)` a metaprogram produced. Which makes it unusable for exactly the case
its documentation names, since a metaprogram that delegates to the built-in
reader has by definition computed the string it wants read.

Either `code-read` should accept a `(slice u8)`, or there should be a way to lift
a runtime string into a string `Code` node. Without one of those, `emit.coil` has
to be rewritten to build `Code` directly — every `put!` becomes quasiquote and
splice — which is a large rewrite of working, tested code for no gain in what it
produces.

## Blocker 3 — a reader is given one file and `coil run` accepts one input

```text
$ coil run payload.txt second.txt --use probe.lang
error: unexpected argument 'second.txt'
```

Doom is 81 `.c` files. cJSON is two. The C model is many translation units in one
program, and the whole-program lowering needs all of them in hand at once: a
single pass over the merged declarations decides which names have definitions,
which `static`s from different files must be kept apart, and which of several
declarations of a name describes its storage. That decision cannot be made one
file at a time.

Two separate things are needed here:

1. `coil run` / `coil build` accepting more than one input file when `--use` is
   in play.
2. The reader being handed all of them — either called once with the whole set,
   or called per file with a way to accumulate across calls and emit one module
   at the end.

Today the reader is called once per file with no way to see the others, and there
is only ever one file.

## Blocker 4 — the reader cannot see the command line

This is what a reader is handed:

```lisp
(read-context "payload.txt" "…the entire source text…" entry)
```

Four elements: the symbol `read-context`, the path, the source, and a role marker
(`entry`). That is all.

A C compiler needs `-I`, `-D`, and `-include` before it can read the first line
of a real program — the header search path, the predefined macros, and the
target description. `-D_FORTIFY_SOURCE=0` and `-DSDL_DISABLE_ARM_NEON_H` are load
bearing for the Doom build specifically.

Arguments after `--` on the command line are accepted by the CLI but do not reach
the reader:

```text
$ coil run payload.txt --use probe.lang -- -Iinclude -DNAME=1
--- reader invoked for payload.txt, role entry      # nothing about -I or -D
```

The reader needs some channel for per-invocation configuration. Whether that is
extra elements in `read-context`, a separate primitive, or something the `--use`
module declares is a design question, but without one there is no way to tell the
C frontend where the system headers are.

## Blocker 5 — the reader runs twice

```text
reader invocation #1 for payload.txt
reader invocation #2 for payload.txt
```

Every reader provider is invoked twice for the same file, on both `coil run` and
`coil build`. For brainfuck that is invisible. For a C frontend it doubles the
work of preprocessing and parsing 81 translation units.

Not a correctness blocker as long as the reader is a pure function of its input,
which this one would be — but it is a straight 2× on build time and it should
probably not be happening.

## Summary

| # | What | Needed for |
| --- | --- | --- |
| 1 | `coil.fs.read-file` undefined and `write-file` hits an unbound `O_CREAT` from a reader; the module's platform-conditional definitions are not expanded | `#include` |
| 2 | `code-read` takes a string `Code` node, not a computed `(slice u8)` | reusing the existing text emitter instead of rewriting it |
| 3 | one input file per invocation, one file per reader call | multi-unit programs — Doom, cJSON, anything real |
| 4 | `read-context` carries only path, source, and role | `-I`, `-D`, `-include` |
| 5 | the reader is invoked twice per file | build time |

1, 3 and 4 are hard blockers: without them a C reader cannot compile any program
that has an `#include`, more than one source file, or a header outside its own
directory — which is every program. 2 decides whether the change to the frontend
is small or large. 5 is a performance bug.
