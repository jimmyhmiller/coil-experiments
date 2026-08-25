# Dependent Coil

> **Status: extremely unfinished research prototype.** This does not provide a
> usable dependent type system for Coil and it is nowhere close to Idris
> compatibility. It supports almost none of the language infrastructure needed
> for real programs. In particular, `Vec`, `Fin`, `Nat`, and equality are
> privileged built-ins rather than ordinary user-defined indexed families.

This experiment implements a dependently typed core as a Coil metaprogram. The
core checker runs during macro expansion, validates dependent source, normalizes
types, and emits ordinary Coil declarations. No compiler modification is needed.

## What is missing

The experiment does **not** currently have the capabilities that would make it
useful as an Idris-like language:

- users cannot define indexed data families such as `Vec` themselves;
- dependent pattern matching is not general and has no coverage/refinement
  machinery comparable to Idris;
- implicit argument inference is a small structural heuristic, not unification;
- there are no metavariables, holes, tactics, proof search, or useful errors;
- termination checking handles only a narrow structural-recursion pattern;
- there are no mutual definitions, interfaces, type classes, namespaces,
  modules, separate compilation, or dependent package APIs;
- dependent values do not interoperate transparently with ordinary Coil;
- runtime lowering consists of a few bespoke emitters for selected types;
- the trusted implementation is a large experimental macro, not a small audited
  kernel with a stable elaborator.

The code below is evidence that a dependent calculus can be hosted at Coil
comptime. It is not evidence that Coil now has practical dependent types.

The kernel currently supports:

- a cumulative, explicitly levelled universe hierarchy (`Type`/`U`);
- dependent functions (`Pi`) and erased dependent functions (`IPi`);
- dependent pairs (`Sigma`) with dependent projections;
- equality, reflexivity, and equality elimination (`J`/transport);
- proof transport/rewrite and decidable propositions (`Not`, `Dec`, `yes`, `no`);
- natural numbers with dependent induction;
- the indexed inductive family `Vec A n` and its dependent eliminator;
- finite indices (`Fin n`) and total, proof-indexed vector lookup (`vget`);
- beta, projection, induction, equality, and vector computation rules;
- alpha-equivalence and fuel-bounded definitional equality;
- explicit and inferred erased applications (`iapp` and `auto-app`), including
  multiple implicit values solved structurally from indexed argument types;
- an Idris-like `def` form with explicit and implicit parameters;
- lowering closed naturals, unary Nat functions, and first-class Nat Sigma pairs
  into ordinary callable/inspectable Coil declarations;
- importing ordinary Coil `i64 -> i64` functions as checked `Nat -> Nat`
  declarations and calling them from dependent code;
- exporting runtime functions whose Sigma result index depends on their runtime
  argument, rather than only specializing compile-time-known indices;
- lowering closed `Vec Nat N` values directly to Coil `(array i64 N)` values so
  the checked index controls native host layout;
- well-founded (`W`) types as a general strictly-positive induction kernel;
- total-by-construction `nat-match` and `vec-match` elaboration forms.
- dependent-record syntax elaborated to nested Sigma types.
- user-defined parameterized algebraic data with checked constructors and
  exhaustive dependent case analysis and strict-positivity checking;
- structural termination checking for recursive calls written through the
  Idris-like `def` form.

```coil
(dependent
  (claim id (Pi A Type (Pi x A A)))
  (define id (fn A Type (fn x A x)))
  (check (app (app id Nat) 7) Nat)
  (check (pair 3 refl) (Sigma n Nat (Eq Nat n 3)))
  (emit-nat answer (app (fn n Nat (plus n 2)) 40)))
```

The less kernel-shaped definition form elaborates into `Pi`/`IPi` and
`fn`/`ifn`:

```coil
(dependent
  (def id [(implicit A Type) (x A)] A x)
  (check (auto-app id 12) Nat))
```

Run the complete focused gate, including expected diagnostic failures:

```sh
python3 scripts/dependent-tests.py --compiler "$(command -v coil)"
```

The calculus is intentionally pure even though the Coil engine hosting it can
perform effectful comptime work. Definitional equality has a reduction limit, so
bad recursive definitions produce a diagnostic instead of hanging compilation.
The higher-level `def` form additionally rejects recursive calls unless their
recursive argument is a predecessor/constructor-field binder introduced by an
exhaustive match. Low-level `claim` plus `define` intentionally exposes the
partial kernel for experimentation; its evaluation remains fuel bounded.

## Boundary and remaining work

This is a real dependent checker hosted by Coil, not an extension of Coil's own
type checker. Dependent declarations must live inside one `dependent` block. The
block erases checked values through explicit emitters, after which ordinary Coil
can call the generated functions and consume generated Sigma representations.

The largest remaining Idris gaps are indexed user-defined data declarations,
general nested-pattern elaboration, higher-order metavariable
solving, mutual/lexicographic termination, interfaces, namespaces and separately
serialized dependent module interfaces. `Nat`, `Eq`, and `Vec` establish the
kernel rules those features must generalize; none is being simulated by unchecked
ordinary Coil code.
