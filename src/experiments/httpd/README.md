# httpd — a small HTTP library

A minimal but complete HTTP/1.1 server library in Coil, built on the standard
library's socket and HTTP parsing modules. It is deliberately small: an
`App` with routes and middleware, plus a blocking server that speaks HTTP/1.1
with `Connection: close`.

## Layout

- `core.coil` — `App`, `Request`, `Response`, route registration (`get!`,
  `post!`, `put!`, `delete!`, `route!`), middleware (`use!`), and dispatch
  (`handle-request`). No sockets: everything here is testable in-process.
- `server.coil` — `listen!`/`serve!`: accepts connections, reads requests into
  a fixed buffer, parses them with `coil.http.parser`, splits the target into
  path and query, dispatches through the `App`, and writes a well-formed
  response with correct `Content-Length`.
- `demo.coil` — the package entry point: hello-world on port 8080.
- `selfcheck.coil` — end-to-end fixture used by `scripts/httpd-integration.py`;
  listens on an ephemeral port, prints `PORT=<n>` on stderr, serves until
  terminated.
- `core_test.coil` — the `httpd` deftest suite (`coil test --suite httpd`):
  routing, method mismatch → 405, miss → 404, middleware short-circuit, and
  query-string splitting.

## Usage

```coil
(import "experiments.httpd.core" :as core)
(import "experiments.httpd.server" :as server)

(defn health [(request (ref core/Request))] (-> core/Response)
  (core/response-json "{\"status\":\"ok\"}"))

(defn main [] (-> i64)
  (let [(mut app) (core/app-new (alloc/malloc-allocator))]
    (core/get! (mut app) "/health" (core/handler-of (primitive/fnptr-of health)))
    ;; middleware returning Some stops the chain before routing
    (core/use! (mut app) (core/Middleware :function (primitive/fnptr-of require-token)))
    (match (server/listen! "127.0.0.1" 8080 app)
      (Ok [running] (server/serve! running))
      (Err [_] 1))))
```

## Semantics

- Routing is exact match on path and method; a matching path with the wrong
  method answers 405, no match at all answers 404.
- Middleware runs in registration order before routes. Returning
  `(Some response)` short-circuits the whole request; `(None)` continues.
- Query strings are split off the request target; handlers see `.path`
  without the query and `.query` without the question mark.
- One request per connection (`Connection: close`), bodies of any size are
  accepted up to what memory allows; requests are parsed by the standard
  library's whole-message parser, so pipelining is not supported.

## Running

```sh
coil test --suite httpd            # unit tests
coil run src/experiments/httpd/selfcheck.coil &
python3 scripts/httpd-integration.py   # end-to-end over real sockets
coil run src/experiments/httpd/demo.coil   # hello world on :8080
```
