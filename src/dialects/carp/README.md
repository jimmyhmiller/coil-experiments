# Carp as a Coil metaprogram

This package implements Carp's compiler pipeline in Coil and exposes it as a
reader dialect. It is not a wrapper around the Haskell compiler, metacarp, or a
Python translator. Reference implementations are development oracles only.

The compatibility contract and pinned upstream revisions are documented in
[`docs/CARP_STATUS.md`](../../../docs/CARP_STATUS.md).

The implementation is organized by semantic phase rather than concentrated in
the reader entry point. In particular, ownership analysis remains a typed,
backend-independent pass so rejection behavior and cleanup plans can be tested
before emitting ordinary Coil syntax. The completed reader metaprogram returns
hygienic Coil declarations and expressions; Coil's normal compiler owns native
lowering and code generation. This package does not implement a Carp-specific C
backend.

Implemented foundations:

- `graph.coil` — dependency-ordered strongly connected components;
- `types.coil` — recursive monotypes, constructor variables, borrow lifetimes,
  structural/representation equality, occurs checking, and destructive
  unification;
- `ownership.coil` — persistent flow states, multi-owner borrow origins,
  control-flow joins, move tracking, reassignment, escape checks, and
  borrow-after-move checks;
- `ir.coil` — stable binding/expression identities and the typed specialized
  expression graph;
- `borrow_check.coil` — evaluation-order-aware analysis of lets, mutation,
  sequences, branches, loops, calls, matches, direct borrows, and
  lifetime-propagating accessor calls;
- `ownership_plan.coil` — any-path/all-path consumption analysis, stable-ID
  validation, binding and temporary deletes, explicit alias moves, parameter
  cleanup, and deduplicated delete-function requirements.

Run their phase-level gate with:

```sh
coil test --suite carp
```

The ownership module is the backend-independent state engine and the borrow
checker consumes it through specialized IR. Type ownership comes from declared
facts (managed names and explicit blit overrides), never source spelling.
By-value call moves are deliberately delayed until every argument expression
has run, matching Carp's evaluation semantics.

Cleanup planning distinguishes a value consumed somewhere from a value consumed
on every exit path. A conditional move therefore retains scope cleanup, while
an all-branch move suppresses it. Owned self-rebinding avoids deleting the old
value twice and still retains the binding's eventual scope delete.
