# Coil live editor protocol

`coil-live-nrepl` is a long-lived native Coil process around the retained
compiler, live metaprogram, JIT generations, and running application world. It
uses nREPL's bencode transport so Emacs can reuse its mature asynchronous
connection machinery without pretending that Coil is Clojure.

Build and start it from the project root:

```sh
coil build src/experiments/live-repl/server.coil -o build/coil-live-nrepl
./build/coil-live-nrepl
```

The server binds loopback on an ephemeral port and writes `.nrepl-port`.
Requests are serialized through the live controller's transaction lane. A type
error returns `eval-error` plus the compiler diagnostic, retains the rejected
candidate for repair, and leaves the accepted code and running world untouched.

## Operations

- Standard transport operations: `describe`, `clone`, `ls-sessions`, `close`.
- `eval`: submit one or more complete top-level Coil forms.
- `load-file`: submit the supplied file contents as a live transaction.
- `coil/state`: exact controller/JIT/runtime snapshot JSON.
- `coil/source`: accepted compiler-session source.
- `coil/pending`: rejected candidate source awaiting repair.

Load `editor/emacs/coil-live.el` after `nrepl-client`, then use `coil-mode`:

- `C-c C-c`: publish top-level form.
- `C-c C-r`: publish region.
- `C-c C-k`: publish buffer.
- `C-c C-z`: inspect current live state.

This is the first vertical slice. Rich parity requires protocol operations for
source-indexed info, completion, references, typed macroexpansion, structured
diagnostic spans, runtime object inspection, generation-aware diffs, and
agent-owned edit transactions. Those belong on the same durable session and
must not invoke a second compiler process.
