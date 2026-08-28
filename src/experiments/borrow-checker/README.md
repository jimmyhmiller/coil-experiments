# Borrow-checked Coil

Import `experiments.borrow-checker.borrow-checker` to enable the ownership
metaprogram and its Rust-like owned containers. Coil's typed affine checker is
the source of truth: types implementing `Drop` are owned, plain scalar values
are copied, `(ref T)` is a shared parameter, `(mut T)` is an exclusive parameter,
and passing an owner by value transfers it. Live owners are destroyed automatically on
normal, branch, match, loop, break, and return exits.

```coil
(import "experiments.borrow-checker.borrow-checker" :use *)

(defstruct User [(id i64)])

(defn main [] (-> i64)
  (let [user (box-new (User :id 42))]
    (with-box-ref [view user]
      (.id view)))) ; user and its allocation are dropped automatically
```

`Box<T>` provides unique heap ownership. `Vec<T>` provides owned growable
storage and recursively drops every live element. User aggregates containing
either type automatically participate in recursive destruction.
`Closure0<Environment, Result>` is a first-class closure whose capture
environment is uniquely owned and recursively dropped; construct it with
`owned-closure0` and invoke it with `closure0-call`.

The scoped `with-box-ref`, `with-box-mut`, `with-vec-ref`, and `with-vec-mut`
forms prevent safe borrowed views from being returned, stored, captured in an
aggregate, or passed to an unverified retaining call. Raw-pointer interop must
be visibly wrapped in `unsafe-borrow`; the upstream lack of general pointer
lifetimes remains tracked in the `coil-bugs` pad rather than hidden.

The safe policy also rejects raw allocation/free, aliasing primitives, inline
LLVM, indirect calls, and unannotated foreign calls. Put the smallest audited
operation—not an entire function—inside `unsafe-borrow` when interoperability
requires one of those proof boundaries.
`experiments.borrow-checker.runtime` is the implementation/unsafe module; normal
programs import only `experiments.borrow-checker.borrow-checker`. Importing the
runtime directly is equivalent to entering an unsafe implementation boundary.

One current Coil compiler defect requires a conservative rule: bind-and-match
of an owned `Option` or `Result` is rejected because upstream cleanup presently
double-drops the moved payload. Match the producing expression directly; that
form is covered under AddressSanitizer and drops the payload once.

Run the complete gate with:

```sh
scripts/borrow-checker-test.sh
```

It executes the sophisticated program and positive unit suite, checks the live
allocation count, and verifies compile-time rejection for use-after-move,
branch/loop ownership disagreement, move or reassignment during a borrow,
conflicting shared/mutable borrows, borrow escape through returns, aggregates,
and calls, raw memory operations, and FFI without an unsafe boundary.
