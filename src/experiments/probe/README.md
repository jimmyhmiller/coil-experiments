# probe — ask a running program questions, in a few lines

```
# coil-module: myapp.probes.stats
call parse-expr { time; }
```

```sh
coil run --use myapp.probes.stats
```

```
probe myapp.probes.stats
  call parse-expr  2 sites in 2 functions
── probe · 384µs · final ──
call parse-expr · time
  6,000 calls  total 349µs  self 266µs  avg 58ns  p50 ~47ns  p99 ~186ns  max 15µs
    0ns █  32ns ▇  64ns ▇  128ns ▁  8.1µs ▁
```

No edit to the application. Nothing compiled in when the probe is not `--use`d.

probe is DTrace's idea rebuilt as a Coil metaprogram. A **reader metaprogram**
reads the `.probe` syntax; the module it produces registers a **whole-program
transform** that rewrites the matching call sites. A probe file *is* a dialect.
Because it runs inside the compiler it knows things no external tracer can: real
parameter names, struct fields, which functions return a `Result`, the file and
line of every call site — and it costs nothing where it does not apply.

**Results never wait for the program to finish.** `print` and `record` write
their line the moment they fire. Aggregations are re-reported by a background
thread (every second by default, `report every 250ms;` to change it) whenever they
changed, and once more at exit. `report every 250ms to "stats.txt";` keeps a file
holding the latest snapshot, for `watch cat stats.txt`.

## The language

```
POINT [during SPAN] [/PREDICATE/] { ACTION; ... }
```

| top-level | |
|---|---|
| a clause (above) | when this happens, do these actions |
| `point NAME = POINT { field = expr; … }` | name a set of calls and give their data friendly names |
| `span NAME = call F;` | a stretch of time: one function's duration |
| `span NAME = enter A .. call B by KEY;` | …or from one call to another, per key |
| `use NAME;` | take another `.probe` file's points and spans (`use http;` is a sibling module) |
| `import coil.module;` | make sure a Coil module is loaded, for `{ coil }` escapes |
| `report [every 500ms] [as json] [to "file"];` | how often aggregations are re-reported, in what format, and where |

**Points.** `call F` fires when a call to F returns (arguments, `result`,
`elapsed`). `enter F` fires before it (arguments only). `mark "name"` fires at a
marker in the source. A `point` or `span` name can stand where a point can.

**Matching F is semantic** — against what the type checker resolved the call to,
through aliases, renames, generic functions and calls a macro wrote. `parse-expr`
(anywhere; ambiguous across modules is an error naming the candidates),
`db/query` or `myapp.db/query` (a module, by full name or dotted suffix),
`myapp.db/*`, `*` (every function in user code), `a | b`.

**Always in scope:** the callee's parameters **by their real names** (`arg0`… for
an extern), `result`, `elapsed`, `wall`, `thread`, `depth`, and the compile-time
facts `site` (file:line:col), `caller`, `module`, `fn`. A predicate that uses only
compile-time facts is decided at compile time: a site that fails it is not
instrumented at all.

**Expressions.** Paths (`req.url`, `result.ok.status`, `result.err`, `path.len`;
struct fields by reflection, `.ok`/`.err` on a Result, `.some` on an Option),
`failed`, literals with units (`5ms`, `64kb`), `= != < <= > >=`, `and or not`,
`starts-with ends-with contains`, `caller in myapp.db/*`, `body[..64kb]`, and
`{ (any coil expr) }` — real Coil with the probe's names in scope. A value that
does not exist (`result.ok.status` of a failed call) makes a comparison false,
prints as `-`, and records as `null`.

**Actions.** `count` · `time` (count, total, self, avg, quantiles, histogram) ·
`sum E` `avg E` `min E` `max E` `hist E` — each takes `by K, K` · `print("… {expr} …")`
· `record { name, name: expr, … }` — both take `to "file"`.

Values are rendered **by their type**: integers, floats, bools, strings, C
strings, slices, structs (field by field) and sums (`Timeout(700)`), recursively.
`record` writes the same shapes as JSON.

## JSON output

Everything probe writes can be JSON, so a tool — a widget, a dashboard, a script —
can consume it. Two ways to ask:

```
report every 500ms as json to "stats.json";      # in the probe file
```
```sh
PROBE_JSON=1 ./app                               # any probe, no rebuild
```

Each line on the stream is then one object:

```json
{"type":"print","text":"load-user ran a query in 1.6ms"}
{"type":"report","elapsed_ns":53274083,"final":false,"aggregations":[
  {"label":"call db/query · time by caller","module":"…","kind":"time","unit":"ns","rows":[
    {"key":["load-report"],"count":3,"sum":32609750,"min":10077917,"max":11268125,"avg":10869916,
     "self":32609750,"p50":11268125,"p99":11268125,"hist":[[8388608,3]]}]},
  {"label":"call db/query · count by caller, fn","kind":"count","unit":null,"rows":[
    {"key":["load-user","query"],"count":12}]}]}
```

- A `by a, b` key is a **list** of its parts, not a joined string.
- Durations are nanoseconds; `unit` is `"ns"` when a value is one, else `null`.
- A report carries **every** row (the text table shows the top twenty).
- `hist` is `[lower bound, count]` per non-empty log₂ bucket; `time` and `hist`
  aggregations carry it along with `p50`/`p99`.
- To a file, the report is the latest snapshot; to stderr, one line per report.
- `record { … }` is already JSON and keeps exactly the fields you wrote.

`demo/probes/json.probe`, and `src/apps/snake/probes/keys-json.probe` for a GUI.

## The cases

Every one of these is a file in `demo/probes/` and is exercised by `scripts/check.sh`.

**1. Stats for a function** — `stats.probe`, `callers.probe`

```
call parse-expr { time; }
call parse-expr { count by caller; count by site; }
```
```
call parse-expr · count by caller
  parse-factor  4,000
  evaluate      2,000
call parse-expr · count by site
  parser.coil:26:19  4,000
  parser.coil:65:5   2,000
```

**2. Only the slow ones, with their arguments** — `slow.probe`

```
call db/query /elapsed > 5ms/ {
  print("{site} slow {elapsed}: {sql}");
  time by caller;
}
```
```
db.coil:20:3 slow 11ms: SELECT u.*, o.* FROM users u JOIN orders o ON …
call db/query /elapsed > 5ms/ · time by caller
  load-report  3 calls  total 33ms  avg 11ms  p50 ~11ms  p99 ~11ms  max 11ms
```
`sql` is `query`'s actual parameter name.

**3. Profile a span** — `frame.probe`, `request.probe`, `decode.probe`

```
report every 500ms;
span frame = call render-frame;

frame               { time; }
call * during frame { time by fn; }
```
```
── probe · 2.01s ──                          <- while the program is still running
frame · time
  121 calls  total 258ms  self 469µs  avg 2.1ms  …
call * during frame · time by fn
  draw-sprites  121 calls  total 109ms  self 82µs  avg 901µs  …
  draw-text     121 calls  total 50ms   self 56µs  avg 417µs  …
```
`during` replaces DTrace's hand-rolled `self->in_frame = 1`. Work done outside a
frame by the same functions is not counted.

A span that is not one function, keyed so overlapping ones stay apart:
```
span request = enter accept-conn .. call send-response by conn.fd;

request { time; time by conn.path; }
request /status >= 500/ { print("{site} request on fd {conn.fd} failed with {status} after {elapsed}"); }
call db/query during request { count by caller; }
```

A span or a moment placed by hand, for when the region is not a function. Without
a probe naming them these compile to their argument and to `0`:
```coil
(import "experiments.probe.marks" :as probe)
(probe/span "decode" (decode-chunk buf))
(probe/mark "vsync-miss" n)
```
```
mark "decode"     { time; hist value; }
mark "vsync-miss" { count; print("{site} vsync miss on frame {value}"); }
```

**4. All file reads** — `reads.probe`, using the point library `files.probe`

```
use files-points;

file-read { print("{site} {path} {bytes}b {elapsed}"); sum bytes by path; }
file-read /failed/ { print("{site} could not read {path}: {result.err}"); }
file-open { count by caller; print("open {path} from {module}/{caller}"); }
```
```
open Coil.toml from coil.fs/read-file          <- inside the bundled stdlib
files.coil:11:10 Coil.toml 293b 64µs
files.coil:11:10 could not read no-such-file.txt: Errno(2)
```
The library is the same language — this is a DTrace "provider", in six lines:
```
point file-open = call coil.os/open        { path = arg0; }
point file-read = call coil.fs/read-file   { bytes = result.ok.len; }
```

**5. Capture all HTTP calls** — `capture.probe`. The whole capture is this clause:

```
call coil.http.client/request {
  record {
    site, caller, wall, elapsed,
    method:   req.method,
    url:      req.url,
    sent:     req.headers,
    status:   result.ok.status,
    received: result.ok.headers,
    body:     result.ok.body[..64kb],
    error:    result.err
  } to "http.jsonl";
}
```
```json
{"site":"net.coil:43:12","caller":"post-echo","wall":1789935178020,"elapsed":447333,"method":"POST","url":"http://127.0.0.1:18473/echo","sent":[{"name":"X-Coil-Demo","value":"probe"}],"status":200,"received":[{"name":"Content-Type","value":"application/json"},…],"body":"{\"echo\": \"hello from coil\"}\n","error":null}
{"site":"net.coil:32:12","caller":"get-status",…,"status":null,"received":null,"body":null,"error":{"Transport":[7,"Could not connect to server"]}}
```
Variations are a line each (`http-errors.probe`, `http-hosts.probe`):
```
http /(failed or status >= 500) and not module in coil.http.client/ { print("{site} {method} {url} -> {status} {result.err}"); }
http { time by { (url-host url) }; }
```
`url-host` is an ordinary Coil function in the demo; the escape calls it.

**6. What falls out** — `alloc.probe`, `errors.probe`, `chunks.probe`

```
call coil.alloc/raw-alloc { sum request.bytes by caller; hist request.bytes; }
call * /failed/           { count by fn; print("{site} {fn}: {result.err}"); }
```
```
probe experiments.probe.demo.errs
  call * /failed/  2 sites in 1 function  (66 skipped: not a Result)
errors.coil:26:24 submit: Timeout(700)
errors.coil:25:14 validate: BadInput(quantity)
```
The second is type-directed: it attaches only to functions that return a `Result`.

A function the program never calls directly — a callback the HTTP client invokes
through a function pointer — is still seen. `(fnptr-of F)` for a probed `F` is
redirected to a generated forwarding function whose one call is then an ordinary
site:
```
call net/count-chunk { count; sum n; print("chunk of {n} bytes via {caller}"); }
```
```
chunk of 13 bytes via count-chunk--probe-thunk
```

## No silent gaps

Every clause reports where it attached, at compile time, and **attaching nowhere
is an error** — a probe that silently matches nothing answers "it never happened"
when the truth is "I never looked". So are an unknown name (the error lists what
is available at that site), an ambiguous function name, reading `result.ok` of a
function that does not return a Result, and a destination file that cannot be
opened (fatal at start-up).

## Setup

Once per project, in `Coil.toml` — a dependency on this package. Its manifest
brings the `.probe` reader with it:

```toml
[dependencies]
probe = { path = "path/to/coil-experiments/src/experiments/probe" }
```

(`src/apps/snake` is a complete example: a GUI game that knows nothing about
probes, one dependency line, and `coil run --use snake.probes.keys`.)

Any `.probe` file under a source root whose first line is `# coil-module: NAME` is
then `--use NAME`. Several `--use`s compose. `PROBE_DUMP=1 coil build …` prints
every rewritten site as the compiler will see it.

```sh
cd src/experiments/probe
coil run --use experiments.probe.demo.frame -- frames    # scenarios: parse db frames server files http errors
scripts/check.sh                                         # every case above, end to end
```

## How it works

| file | |
|---|---|
| `lang.coil` | declares the reader provider — the module `[readers]` names |
| `reader.coil` | the DSL → an s-expression **spec** + the generated module's source (cells for aggregations/destinations/spans, `probe-init`, the transform registration), handed to the built-in reader |
| `engine.coil` | the transform: semantic matching, site rewriting, expression compilation, type-directed rendering, the match report. The spec format is documented at its top |
| `rt.coil` | the runtime: aggregations, spans, per-thread state, destinations, the reporter thread |
| `marks.coil` | `(probe/span …)` / `(probe/mark …)` |

What one site becomes (`PROBE_DUMP=1`), for `call parse-expr { time; }`:

```coil
(let* [probe-site-myapp.probes.stats "0"
       probe-t0      (experiments.probe.rt.call-begin!)
       probe-call    (parse-expr c)
       probe-elapsed (experiments.probe.rt.call-end! probe-t0)
       probe-post    (if (experiments.probe.rt.enter!)
                         (do … (experiments.probe.rt.agg-time! (myapp.probes.stats.probe-agg-0) probe-elapsed) …
                             (experiments.probe.rt.leave!))
                         0)]
  (experiments.probe.rt.ret probe-call))
```

Things the engine has to respect, each learned the hard way:

- A semantic transform's output is **not macro-expanded**: templates use primitive
  forms only (`let*`, `if`, `do`, `loop`, `match`, `(.f x)`, `(: e T)`).
- Transforms run to a **fixpoint**. A site is recognized by its first binder and
  never rewritten twice; several probe modules on one call recognize each other's
  sites; the match report is produced by the round that changes nothing.
- The type of a synthesized expression is unknown when it is built. A value to be
  rendered goes through a generic no-op, `show-marker`; the **next round** asks the
  type checker what it is (`type-of`) and replaces it — struct by struct, until
  only scalars remain.
- `code-decl` must be given the **call node**, not the head symbol: only then does
  it resolve generic functions and calls a macro in another module introduced.
- Argument expressions that are symbols or literals are read again rather than
  bound; binding a by-reference value changes how it is passed.
- Nodes are rebuilt with `code-list-like`, and only on the path to a rewrite, so
  untouched code keeps its identity, spans and hygiene.
- The runtime is self-contained on libc and guarded per thread, so a probe on
  `raw-alloc` does not fire on the allocations its own bookkeeping makes.

## Not covered

- **Attaching to a running process.** A probe is a rebuild. (The stateful JIT /
  live-hooks work is the route to pushing a probe into a running program.)
- **`impl` methods.** `code-decl` answers `:unresolved` for method calls, so
  clauses attach to functions and externs only, and `mod/*` does not include a
  module's methods. Filed in the `coil-feature-requests` pad.
- **Below the libc boundary.** Coil calls down to `open`/`read`/`connect`, nothing
  under them; and calls *inside* a prebuilt unit (e.g. `coil.jit`) are linked, not
  recompiled, so they cannot be rewritten.
- **Span-scoped variables** (`req.bytes += n`) and **`matches`** (regex). The
  parser rejects both with an explicit error. Per-request byte totals for a
  streamed body are reachable today by probing the chunk callback (`chunks.probe`).
- **`{ coil }` escapes are not macro-expanded** (they are transform output): use
  function calls and primitive forms. Function names in an escape are resolved
  program-wide, so they mean the same thing at every site.
- `ok`, `err`, `some` and `len` are path words; a struct field with one of those
  names is shadowed.
- `time` on a recursive function reports inclusive time per call, so `total`
  counts nested calls twice; `self` does not.
