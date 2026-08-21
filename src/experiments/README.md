# Experiments

Research milestones that demonstrate ideas still relevant to Coil's design but are
not part of the standard library or compiler surface:

- [`gc-dialect/`](gc-dialect/) — explicit-root garbage collection as a dialect.
- [`transparent-gc/`](transparent-gc/) — the follow-on transform that inserts roots.
- [`heap-inspector/`](heap-inspector/) — automatic heap-struct census, reflection,
  and JIT-queryable inspection as a whole-program transform.

The production-scale demonstration of transparent GC lives in
[`src/apps/mini-scheme/`](../apps/mini-scheme/).
