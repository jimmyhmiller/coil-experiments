# Concurrency metaprograms: execution models, not just syntax

These experiments implement three concurrency models in ordinary Coil without
compiler changes:

1. async/await with resumable activation records;
2. Go-style CSP with lightweight processes and bounded channels;
3. Oz-style dataflow threads with single-assignment logic variables.

The important result is not that Coil can spell `await`, `go`, or `thread`. Each
construct changes execution. No experiment creates a pthread or blocks an OS
thread. A shared cooperative runtime parks a lightweight task when its dependency
is unavailable, runs other ready tasks, and re-enqueues the parked task when the
dependency becomes available.

These are substantial executable prototypes, not production runtimes. They have
real scheduling, wait queues, wakeups, backpressure, completion, deadlock
detection, and lifecycle handling, but intentionally narrow value and operation
sets.

## Shared cooperative scheduler

Source: `src/experiments/coop/scheduler.coil`

Every logical computation embeds a `Task` containing:

- a step-function pointer and opaque activation-record pointer;
- a program counter (`state`);
- runnable, queued, and completed flags;
- links for the scheduler queue and one wait queue.

`Scheduler` owns an intrusive FIFO ready queue. One scheduler turn removes one
task, invokes one state-machine transition, and re-enqueues it only if it remains
runnable. `task-park!` places it on a dependency's wait queue instead. Waking a
dependency moves its waiters back to the ready queue. Thus a suspended operation
uses memory for a task record, but no native thread and no CPU while parked.

```text
                         dependency becomes ready
                                  │
                                  ▼
┌─────────────┐  dequeue   ┌─────────────┐
│ Ready queue │───────────▶│ Task.step() │
└──────▲──────┘            └──┬───────┬──┘
       │                       │       │
       │ yield/continue        │       │ complete
       └───────────────────────┘       ▼
                               ┌─────────────┐
                   unavailable │    Done     │
                         ┌─────▶└─────────────┘
                         ▼
                  ┌────────────┐
                  │ Wait queue │
                  └────────────┘
```

`scheduler-run!` returns `true` when all tasks complete. It returns `false` when
the ready queue is empty but live tasks remain, making deadlock/idle explicit
instead of hanging a native thread.

This scheduler is intentionally single-threaded. Operations on futures,
channels, and logic-variable wait queues are therefore atomic without locks.

## 1. Async/await

Source: `src/experiments/async/async.coil`

Example: `src/experiments/async/demo.coil`

### What the metaprogram generates

`defasync-i64` generates three concrete artifacts:

1. a heap activation-record struct containing the future, arguments, and locals
   that must survive suspension;
2. a step function that resumes from the task's program counter;
3. a launcher that allocates the record and schedules its embedded task.

An async call returns immediately with a `Future`. It does not execute the body
to completion and does not create a native thread.

At an await transition, `future-await!` first records the continuation state. If
the future is incomplete, it links the current task into that future's waiter
queue and returns control to the scheduler. Completion stores the result exactly
once and wakes every waiter. When a waiter runs again, it resumes at the recorded
state and reads the result.

```text
async call ──▶ allocate machine ──▶ enqueue ──▶ return Future

await incomplete ──▶ save PC ──▶ park on Future
                                      │
producer completes ──▶ store result ──┴──▶ wake ──▶ resume at PC
```

### Real example

The invoice example starts three delayed operations before awaiting any result:

```coil
(set! (.price machine)    (delayed-value (.scheduler task) 41207))
(set! (.stock machine)    (delayed-value (.scheduler task) 20043))
(set! (.shipping machine) (delayed-value (.scheduler task) 31300))
```

The delays are logical scheduler ticks, so the test is deterministic: all three
operations make progress round-robin. The invoice task parks on an incomplete
price future; it later resumes, saves the price across another suspension, waits
for shipping, and completes. The example asserts both the result and the exact
14-turn interleaving trace.

Output:

```text
invoice total=2507 stock=43
scheduler steps=14 (overlapped logical delays)
```

### Advantages

- An incomplete await suspends a computation, not an OS thread.
- Activation records retain locals safely across multiple suspension points.
- Multiple independent operations overlap on one scheduler.
- FIFO scheduling makes this example deterministic and testable.
- Futures support multiple waiters and wake all of them on completion.

### Limits / route to production

- The macro exposes transitions explicitly; it does not yet transform an
  arbitrary direct-style Coil function into a state machine.
- Arguments, saved values, and results are currently specialized to `i64`.
- There are no errors, cancellation, deadlines, structured scopes, or async I/O
  reactor integration.
- The scheduler is single-threaded, with no work stealing or multicore execution.
- Memory ownership is conventional rather than statically checked.

## 2. Go-style CSP

Source: `src/experiments/csp/csp.coil`

Example: `src/experiments/csp/demo.coil`

### What the metaprograms generate

`defprocess` compiles a process DSL into a resumable step function. Its state
clauses include send, receive, assignment, branch, close, and completion.
`go` initializes a lightweight task with that generated process and a typed
context. It does **not** start a pthread.

The `i64` channel is a bounded ring buffer with separate sender and receiver wait
queues. A send has three outcomes:

- buffer space: commit the value and wake one receiver;
- full buffer: park the sender without advancing its program counter;
- closed channel: take the generated closed transition.

Receive is symmetric. An empty open channel parks the receiver; consuming a value
wakes one sender. Closing wakes both queues. Because a parked operation leaves its
program counter unchanged, wakeup retries the same operation rather than silently
losing a send or receive.

### Real example

The fulfillment pipeline runs 14 lightweight processes on one native thread:

- one producer sends orders 1–20;
- twelve workers compete for orders and send their squares;
- one collector receives all results and closes the output channel.

Both channels have capacity two. The example asserts the computed total, that all
14 tasks completed, and—critically—that channel operations actually parked and
woke tasks. This proves bounded backpressure occurred rather than the channels
being decorative queues.

```text
fulfilled=20 total=2870
```

### Advantages

- Lightweight Go-like processes multiplex over one scheduler.
- Bounded queues impose real backpressure and bounded storage.
- Application processes communicate through messages rather than shared data.
- Close behavior wakes blocked peers and permits buffered values to drain.
- The generated state machines preserve operations correctly across parking.

### Limits / route to production

- Channels carry only `i64`; production code needs generated typed channels.
- There is no `select`. Correct select requires registration on multiple queues,
  one atomic winner, and removal of losing registrations.
- There is no cancellation, process failure propagation, or supervision tree.
- Scheduler fairness is FIFO by transition, not Go's runtime behavior.
- No multicore scheduler, work stealing, or nonblocking network poller exists.

## 3. Oz-style dataflow concurrency

Source: `src/experiments/dataflow/dataflow.coil`

Example: `src/experiments/dataflow/demo.coil`

### What Oz actually means

In Oz, `thread S end` forks a cheap dataflow thread and the current thread
continues immediately. Evaluation of an operation that needs an unbound logic
variable transparently suspends that dataflow thread. Binding the variable makes
dependent threads runnable. Ordinary `=` performs unification; it is not mutable
assignment.

That description follows the
[Mozart 1.4 concurrency tutorial](http://mozart2.org/mozart-v1/doc-1.4.0/tutorial/node8.html).
Its worked example shows one thread repeatedly resuming as `X0`, `X1`, `X2`, and
`X3` are bound, then suspending on the next dependency. Oz also supports
structural values and streams; this experiment implements the scalar core only.

### Coil adaptation

The surface is flat: declarations, threads, bindings, and ordinary reads share
one lexical region. There is no nested equation-vector API:

```coil
(oz [quantity unit-price subtotal tax-rate tax before-shipping shipping total]
  (thread (= subtotal (* quantity unit-price)))
  (thread (= tax (/ (* subtotal tax-rate) 100)))
  (thread (= before-shipping (+ subtotal tax)))
  (thread (= total (+ before-shipping shipping)))
  (= shipping 1200)
  (= tax-rate 8)
  (= unit-price 2500)
  (= quantity 3)
  (let [answer total] ...))
```

`oz` allocates one `DataflowVar` per declared name and compiles every `thread`
equation into a `DataflowRule` state machine. Each input read is a potential
suspension point. Reading an unbound variable adds the current lightweight task
to that variable's waiter queue. Unification performs one of three transitions:

- unbound → bound: store the value and wake all readers;
- same value: return `AlreadyBound`;
- different value: return `Conflict(existing, attempted)` without mutation.

Before any external input is bound, the generated program gives every equation a
scheduler turn and asserts that all four remain live with an empty ready queue:
they genuinely suspended on missing data. Inputs are then unified in an order
unrelated to the dependency graph. Wakeups propagate through subtotal → tax →
before-shipping → total. Ordinary use of `total` resolves the graph and yields:

```text
quote subtotal=7500 tax=600 total=9300
```

The final conflicting `quantity = 4` is also checked to ensure single assignment
cannot be overwritten.

### Why this has Oz's core execution semantics

- `thread` creates independently schedulable lightweight work.
- Using an unbound input parks only that work, not the native thread.
- Binding is single-assignment unification and wakes dependents.
- Source order of bindings does not determine evaluation order.
- A permanently unresolved dependency is reported by scheduler deadlock rather
  than consuming CPU or hanging inside a condition variable.

This is **not full Oz**, and the distinction matters. It currently lacks logic
variable aliasing and structural unification, records, lists with unbound tails,
pattern matching on partial values, streams, higher-order procedures, exceptions,
constraints, priorities, and distributed dataflow. Its equation compiler accepts
only scalar `i64` addition, multiplication, and percentage calculations. Those
are language breadth limitations; the implemented suspension/wakeup mechanism is
the relevant dataflow execution model.

### Advantages

- Dependencies are expressed as data relationships rather than task ordering.
- Deterministic single assignment removes write races.
- Suspended computations consume no CPU and no OS thread.
- Bind order can vary without changing a deterministic graph's result.
- Conflicting unification is explicit and non-destructive.

### Limits / route to production

- Implement a term heap and union-find logic variables for aliasing and recursive
  structural unification.
- Generate general dataflow-thread continuations rather than the current binary
  scalar equation subset.
- Add partial records/lists and wake on the structural information required by a
  pattern match, enabling real Oz stream programs.
- Add failed values, exception propagation, cancellation, and useful deadlock
  diagnostics.
- Add a parallel scheduler while preserving atomic unification and deterministic
  declarative behavior.

## Running and verification

The repository setup installs a full LLVM-enabled Coil toolchain:

```sh
bash .agents/setup

coil run src/experiments/async/demo.coil
coil run src/experiments/csp/demo.coil
coil run src/experiments/dataflow/demo.coil

python3 scripts/experiments.py --only experiments/async
python3 scripts/experiments.py --only experiments/csp
python3 scripts/experiments.py --only experiments/dataflow
```

The examples are included in the repository's blessed experiment corpus. Their
runtime assertions verify completion, results, and model-specific behavior—not
only printed syntax: the async interleaving trace, CSP parking/wakeup, and initial
Oz dataflow suspension are all checked.
