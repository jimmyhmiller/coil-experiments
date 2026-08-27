# Trait result and forwarding notes

## Forwarding workaround

The original `bounded-outer` reproduction forwarded its `T: Measure` bound to
a second generic helper. That compiler path still rejects the bound, but it is
not needed by the Ohm implementation: calling the trait method directly from
the already-bounded function is clearer and typechecks. The checked-in fixture
now uses that direct form, and `coil check
tests/ohm/trait-bound-forwarding-repro.coil` exits 0. Production Ohm code must
prefer this direct trait dispatch rather than lower-level representation APIs.

## Historical forwarding diagnostic

`tests/ohm/trait-bound-forwarding-repro.coil` contains one trait and two generic
functions. Both functions declare the identical `T: Measure` bound. The outer
function explicitly instantiates the inner function with that same `T`:

```coil
(defn bounded-inner [(T Measure)] [(value T)] (-> i64)
  (measure value))

(defn bounded-outer [(T Measure)] [(value T)] (-> i64)
  (bounded-inner [T] value))
```

Run:

```sh
coil check tests/ohm/trait-bound-forwarding-repro.coil
```

Current result:

```text
'T' does not implement 'tests.ohm.trait-bound-forwarding-repro.Measure'
(required by '...bounded-inner' bound on 'T')
```

Expected: the file typechecks. `bounded-outer` already proves exactly the bound
required by `bounded-inner`; explicit type application should forward that
evidence.

The generic semantic evaluator no longer relies on this forwarding pattern.

There is a distinct, still-active generic-result reproduction in
`tests/ohm/generic-result-trait-repro.coil`:

```coil
(deftrait Convert [Self E]
  (convert [(value Self)] (-> E)))

(defn run-convert [(T Convert) E] [(value T)] (-> E)
  (convert value))
```

`coil check tests/ohm/generic-result-trait-repro.coil` reports that the body has
type `<T as Convert>::E` rather than the declared `E`. There is currently no
accepted bound syntax that equates the trait's `E` argument with the function's
`E`; `(T (Convert E))` is rejected because a bound expects a symbol. This is why
the working semantic action ABI temporarily uses `i64` results/handles.
