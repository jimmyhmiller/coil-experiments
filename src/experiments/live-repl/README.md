# Live REPL

This package exposes the heap-inspector live controller as an nREPL-compatible
native server. See [`../../../docs/LIVE_REPL.md`](../../../docs/LIVE_REPL.md) for
the protocol, Emacs commands, transaction semantics, and roadmap.

The bencode codec is independent of the compiler/runtime and has focused tests.
`protocol.coil` is the semantic boundary: editor and agent operations must go
through it instead of reconstructing live state from source files.
