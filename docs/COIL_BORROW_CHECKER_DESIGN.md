# Applying the Carp borrow checker to Coil

## Purpose

The Carp metaprogram contains a flow-sensitive ownership checker that can form
the basis of an optional ownership mode for ordinary Coil. The state engine is
already largely independent of Carp syntax, but the checker is not a pass that
can simply be enabled for Coil: it currently consumes Carp's specialized IR,
uses Carp's managed-type facts, and produces cleanup actions for the Carp
emitter.

The recommended design is to preserve the state engine, define an explicit
ownership contract for Coil, and run a new Coil-facing analysis after type
checking and monomorphization. The first version should diagnose ownership
errors without changing destruction behavior. Automatic cleanup should be a
later, separately testable phase.

## Existing reusable pieces

The implementation is split across four responsibilities:

- `src/dialects/carp/ownership.coil` contains persistent flow state, ownership
  origins, active borrows, moves, reassignment, escape checks, and branch
  joins. This is the most reusable component.
- `src/dialects/carp/borrow_check.coil` walks `SpecializedExpr` in evaluation
  order and applies ownership operations. Its algorithms are reusable, but its
  IR traversal is Carp-specific.
- `src/dialects/carp/ownership_plan.coil` derives moves, borrows, and cleanup
  points from stable expression and binding identities. Its planning rules can
  be generalized after Coil has an ownership contract.
- `src/dialects/carp/managed.coil` derives ownership facts from Carp interfaces
  such as `delete` and `blit`. Coil needs its own source of these facts.

The useful boundary to extract is an ownership analysis library that knows
nothing about either Carp or Coil AST nodes. A language adapter should translate
typed operations into calls on that library.

## Required Coil ownership contract

Before implementing a compiler pass, Coil must define what its types and
function boundaries mean. Without this contract, a checker could be internally
consistent while rejecting valid programs or approving use-after-free.

### Value classifications

Every monomorphic type must receive one of these classifications:

- **Copy**: duplicating bits creates an independent valid value. Integers,
  booleans, and suitable immutable aggregates normally belong here.
- **Owned**: exactly one live owner is responsible for destruction or transfer.
- **Shared borrow**: a non-owning alias that permits reads for a bounded
  lifetime.
- **Mutable borrow**: an exclusive non-owning alias that permits mutation for a
  bounded lifetime.
- **Unsafe/raw**: the compiler cannot prove ownership behavior. Raw pointers,
  erased pointers, arbitrary pointer casts, and unannotated foreign values
  normally belong here.

`ptr`, `ref`, and `mut` are not sufficient by themselves to infer all of these
properties. In particular, a pointer does not say whether it owns an allocation,
and a function accepting a value does not currently state whether it consumes
or merely observes it.

### Function effects

Each parameter and result needs a resolved ownership mode. A concrete design
could use explicit type constructors or attributes equivalent to:

```coil
(defn consume [(value (own String))] (-> i64) ...)
(defn inspect [(value (ref String))] (-> i64) ...)
(defn mutate [(value (mut String))] (-> i64) ...)
```

The exact syntax is a language-design decision. Internally, the compiler needs
at least `copy`, `consume`, `shared-borrow`, `mutable-borrow`, and `unsafe`.
Result metadata must also express when a returned borrow originates from a
particular argument. This is necessary for accessors and iterator-like APIs.

### Destruction and copying

Owned types need resolved operations rather than name-based conventions:

- a destructor, if the compiler will eventually insert cleanup;
- a copy operation when explicit copying is legal;
- a declaration that the type is bitwise-copyable when no operation is needed.

These facts should be part of checked type metadata. The analysis must not guess
ownership from source spelling or from the existence of a function whose name
happens to end in `copy` or `destroy`.

## Compiler placement

The pass should run after name resolution, type checking, and monomorphization,
and before backend lowering:

```text
Coil source
  -> expansion and resolution
  -> type checking
  -> monomorphization
  -> ownership fact resolution
  -> borrow checking
  -> optional ownership/cleanup planning
  -> existing backend lowering
```

Concrete types are required to decide whether a generic value is copied or
owned. Resolved bindings are required to distinguish shadowed variables and to
connect returned borrows to their origins. Running on surface syntax would lose
both guarantees.

## Stable analysis IR

The current Carp checker relies on stable expression and binding IDs. Coil
should either expose equivalent IDs in its monomorphic IR or translate that IR
to a compact ownership IR.

A compact ownership IR is preferable if Coil's backend IR changes frequently.
It needs to represent:

- literals and bitwise-copyable values;
- binding introduction, read, move, reassignment, and address-taking;
- shared and mutable borrows;
- direct and indirect calls with resolved argument modes;
- left-to-right evaluation order;
- blocks, conditionals, loops, matches, breaks, and returns;
- stack allocation, heap allocation, and explicit destruction;
- globals and static storage;
- closure capture modes and closure escape;
- raw pointer operations, casts, inline backend operations, and FFI boundaries.

Each operation needs a stable site ID. Each lexical binding needs a stable
identity independent of its spelling. Control-flow exits must be explicit so
the checker can validate and join every reachable state.

## Generalizing the state engine

Move the reusable definitions and transitions from
`experiments.carp.ownership` into a neutral compiler library. The neutral API
should accept opaque binding/site IDs and resolved ownership facts. It should
not import Carp IR or Carp types.

The core operations should include:

- introduce an owned or copyable binding;
- borrow a binding or temporary, with shared or mutable mode;
- consume/move a value;
- read or mutate through an allowed access path;
- reassign a binding;
- end a lexical scope or temporary lifetime;
- join branch states;
- validate loop back-edges;
- validate return, break, capture, and global escape;
- report use-after-move, borrow-after-move, conflicting borrow, and escaping
  borrow diagnostics.

Diagnostics should carry the original declaration site, the operation that
created the conflicting borrow or move, and the failing use site. The engine
can return structured errors; the Coil adapter should render source locations.

## Coil-specific traversal

The Coil adapter must follow actual evaluation order. For a call, evaluate the
callee and every argument first, establish temporary borrows as required, and
only then commit by-value moves. Delaying moves is important for calls where a
later argument borrows a value also passed by value.

For control flow:

- `if` and `match` analyze each reachable arm and join the resulting states;
- a value moved on only some paths remains conditionally live and cannot be
  consumed again without proof;
- loops require a fixed-point or a conservative back-edge check so successive
  iterations cannot reuse a moved value;
- `break`, return, and other early exits retain their own outgoing states;
- reassignment must reject active borrows and must establish a new ownership
  generation for the binding.

Closures require explicit capture classification. Copy captures copy; owned
captures move; borrow captures are valid only when the closure cannot outlive
the owner. Escaping closure analysis must include returns, globals, heap storage,
and calls whose effect metadata permits retaining the closure.

## Unsafe and FFI boundaries

The checker must be honest about operations it cannot prove. The initial safe
mode should reject or require an explicit unsafe region for:

- conversion between integers and pointers;
- casts that erase pointee or lifetime information;
- ownership reconstructed from `ptr i8`;
- foreign calls without ownership annotations;
- storing borrowed pointers in untracked memory;
- calling function pointers without a checked effect signature;
- manual destruction that cannot be connected to a tracked owner.

An unsafe operation does not need to make the entire function unanalyzed. It
should create a narrow proof boundary with explicit preconditions and
postconditions. Values leaving that boundary need a declared ownership mode.

FFI declarations should eventually allow parameter/result annotations such as
borrowed for call duration, consumed, returned owner, returned static borrow,
and returned borrow tied to argument N.

## Phased implementation

### Phase 1: specification and fixtures

Define the ownership modes, function effects, lifetime relationships, unsafe
boundary, and interaction with existing `ptr`, `ref`, `mut`, allocation, and
destruction. Add accepted and rejected Coil examples before implementing the
pass.

### Phase 2: neutral ownership engine

Extract the Carp-independent state engine without changing Carp behavior. Run
the existing Carp ownership and ownership-plan suites against the extracted
library. This prevents the Coil work from silently regressing Carp.

### Phase 3: diagnostic-only safe subset

Translate monomorphic Coil functions containing locals, blocks, calls,
conditionals, loops, matches, and returns. Support copy values, owned locals,
shared borrows, mutable borrows, and consuming calls. Require explicit unsafe
boundaries for raw pointers and FFI. Do not insert cleanup yet.

### Phase 4: closures and aggregates

Add aggregate field paths, partial access rules, closure captures, indirect
calls, generic aggregate ownership, globals, and statics. Resolve copy and
destructor operations as typed metadata.

### Phase 5: cleanup planning

Generalize `ownership_plan.coil` to emit backend-independent cleanup actions for
every normal and early exit. Verify that explicit destruction and inserted
destruction cannot target the same ownership generation. Keep this phase
separate from borrow acceptance so each can be tested independently.

### Phase 6: opt-in production mode

Expose the checker through a module, package, function, or project-level option.
Existing Coil remains compatible unless ownership checking is requested.
Migration diagnostics should explain missing annotations rather than guessing.

## Test strategy

Testing needs both state-engine tests and end-to-end compiler tests.

The minimum matrix includes:

- use, borrow, or mutate after move;
- shared/shared and shared/mutable borrow combinations;
- reassignment with and without active borrows;
- conditional and all-path moves;
- loop-carried moves and borrows;
- early returns and breaks;
- call argument evaluation order;
- returned borrows tied to parameters;
- local borrow escape through returns, aggregates, closures, globals, and FFI;
- owned closure capture and nonescaping borrow capture;
- explicit destruction followed by use or second destruction;
- generic functions instantiated with copy and owned types;
- raw-pointer and FFI unsafe boundaries;
- cleanup exactly once on every reachable exit.

Differential tests should keep the Carp adapter and Coil adapter aligned on
language-neutral cases. Debug-runtime and sanitizer runs should supplement, not
replace, static rejection tests.

## Compatibility and rollout

Applying ownership rules to all existing Coil code immediately would be both
disruptive and unsound: existing APIs do not declare enough intent for the
checker to distinguish borrowing from consumption. The checker should therefore
start opt-in and diagnostic-only.

Success for the first production milestone means that an annotated safe subset
of Coil receives deterministic acceptance or source-located rejection, raw and
foreign operations have explicit unsafe boundaries, and enabling the checker
does not change runtime behavior. Automatic destruction is a later milestone
and must not be used to compensate for an underspecified ownership contract.

## Principal risks

- Inferring ownership from existing types would create accidental semantics.
- Pointer casts can invalidate guarantees unless isolated as unsafe.
- Cleanup insertion can double-free values already destroyed manually.
- Monomorphization may clone or erase identities needed by diagnostics.
- Closure and FFI effects can hide escapes unless their contracts are explicit.
- A checker coupled directly to backend IR would become brittle as lowering
  changes.

The central design rule is therefore: reuse the proven flow-state machinery,
but make Coil's ownership semantics explicit before adapting the traversal or
inserting any cleanup.
