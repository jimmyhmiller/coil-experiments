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
  (let [user (box-new (User :id 42))
        view (box-borrow [User] user)]
    (.id view))) ; user and its allocation are dropped automatically
```

`Box<T>` provides unique heap ownership. `Vec<T>` provides owned growable
storage and recursively drops every live element. User aggregates containing
either type automatically participate in recursive destruction.

The current Coil compiler checks affine ownership, moves, branch joins, loop
back-edges, and mutable call boundaries. It does not yet attach lifetimes to raw
`(ptr T)` results, so `box-borrow` and `vec-get` views must not be returned or
stored beyond their owner. That upstream compiler gap is tracked in the
`coil-bugs` pad rather than hidden by this package.
