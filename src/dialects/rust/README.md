# CoilRS: a Rust-like surface syntax for Coil

Status: implemented reader, structured parser, conservative canonical renderer,
tree converter, and self-host integration gate.

The implementation includes the lossless native escape, tree
conversion/materialization, and dedicated syntax for the constructs in this
document. The canonical renderer proves each converted form reconstructs the
same native syntax tree before using dedicated syntax; forms it cannot prove use
`coil_item` automatically. This is not an error or a lossy approximation—the
escape is the compatibility representation for macros, future forms, malformed
reader fixtures, and deliberately unusual syntax.

CoilRS is a different spelling of Coil, not a new language and not a Rust
frontend. The reader turns a `.coilrs` file into ordinary Coil `Code`; after that,
the normal loader, macro expander, checker, metaprograms, and backends run
unchanged. In particular, CoilRS does not add Rust ownership, borrowing,
lifetimes, implicit returns, or method-call dispatch.

The design has two goals:

1. Ordinary Coil should look comfortably Rust-like.
2. Every Coil program must be representable, including forms invented by user
   macros after this reader was written.

The second goal is guaranteed by the native escape:

```rust
coil {
    (any ordinary Coil form, copied verbatim)
}
```

A converter may use pleasant CoilRS syntax for forms it knows and a `coil` escape
for everything else. Consequently conversion is total and this round trip is
required to preserve the native Coil syntax tree:

```text
Coil source -> Coil Code -> canonical CoilRS -> CoilRS reader -> Coil Code
```

Whitespace, comments, delimiter choice, and numeric spelling are not syntax-tree
data and are not promised to survive. Identifier identity, literal values, form
shape, ordering, and quoted syntax are. The canonical renderer must be
deterministic and idempotent.

## A complete example

```rust
module example::points;

use coil::io::{stdout, print_str};
use coil::alloc as alloc;

#[derive(Eq, Hash)]
struct Point {
    x: i64,
    y: i64,
}

impl Point {
    fn new(x: i64, y: i64) -> Point {
        Point { x: x, y: y }
    }

    fn sum(p: Point) -> i64 {
        p.x + p.y
    }
}

fn main() -> i64 {
    let mut total = 0;
    for i in 0..10 {
        let p = Point::new(i, i * 2);
        total = total + sum(p);
    }
    println("total={}", load(total));
    0
}
```

It lowers to the same forms one would write in ordinary Coil, including explicit
`(mut total)`, `(load total)`, `store!`, `for`, constructors, and calls. Braces
sequence expressions and yield their final expression. A trailing semicolon
discards an expression's value for sequencing purposes; it does not change Coil's
type rules.

## Lexical syntax

Line comments are `// ...`; nested block comments are `/* ... */`. Doc comments
are `/// ...` and lower to Coil `;;` documentation attached to the following
declaration. The canonical renderer uses four-space indentation.

CoilRS accepts Coil's integer and floating literals, including radix prefixes and
underscores. It accepts `true`, `false`, strings, C strings (`c"..."`), character
literals (`'x'`, `'\n'`, `'\u{03bb}'`), and keywords (`:else`, `:hot`). Character
literals lower to Coil's `#\...` form.

Ordinary identifiers may contain ASCII letters, digits, `_`, `-`, `?`, and `!`,
but may not begin with a digit. Thus existing names such as `empty?`, `push!`, and
`return-from` need no renaming. A backtick identifier allows every other Coil
symbol spelling:

```rust
let `+` = add_function;
`strange name`(1);
```

`a::b::name` lowers to Coil's qualified symbol `a.b/name`: all but the final
segment form the module alias/name, and the final segment is the member. A module
declaration maps every `::` to `.`, so `module my::app::main;` becomes
`(module my.app.main)`. This intentionally leaves `/` available only inside a
backtick identifier or a native escape.

Reserved words may be used as names when backtick-quoted. No identifier is
case-folded.

## Modules, imports, and exports

```rust
module my::app;

use coil::io::*;
use coil::io::{print, println};
use coil::io as io;
use coil::io::{print as io_print};
use coil::io::* except { print };
pub use coil::io::*;                 // adds :reexport

export { main, helper };
```

These lower to `module`, `import`, and `export`. For less common combinations,
an import accepts clauses after `with`:

```rust
use "coil.io" with {
    as: io,
    use: *,
    exclude: [print],
    rename: [[println, writeln]],
    reexport: true,
};
```

The quoted module spelling is exact. The structured spelling covers every native
`import` clause without assigning new meaning to one particular combination.

## Types

Built-in scalar and named types retain their Coil names: `i8`, `u64`, `f32`,
`bool`, `void`, `Code`, `Point`. Type application uses angle brackets:

```rust
Option<i64>                 // (Option i64)
ptr<u8>                     // (ptr u8)
mut<Point>                  // (mut Point), a Coil mutable place/reference type
slice<u8>                   // (slice u8)
array<u8, 64>               // (array u8 64)
vec<f32, 4>                 // (vec f32 4)
dyn<Writer>                 // (dyn Writer)
fnptr<c, [i64, i64], i64>   // (fnptr c [i64 i64] i64)
```

The optional Rust-looking aliases `*const T`, `*mut T`, and `&mut T` are not in
version 1: they would falsely imply distinctions or guarantees Coil does not
have. Canonical output always uses the explicit constructors above.

Generic parameter packs keep Coil's ellipsis: `Args...`. Bounds use `T: Eq +
Hash`. A declaration can therefore spell parameters as `<T, U: Show, Args...>`.

## Declarations

### Constants and functions

```rust
const ANSWER = 42;
const MASK: u64 = 0xff;

fn add(x: i64, y: i64) -> i64 {
    x + y
}

fn show_all<T: Show, Args...>(x: T, args...: Args...) -> i64 {
    coil { (consume x args...) }
}
```

These lower to `const` and `defn`. A parameter may be written `x: mut<T>` when
the native signature expects `(x (mut T))`. Variadic C parameters use `...` in an
`extern` declaration; Coil type/value packs retain their native `...` spelling.

Coil annotations use Rust attributes. Their contents are CoilRS expressions:

```rust
#[inline(Always)]
#[http::route(Get("/users"))]
fn users() -> i64 { 0 }
```

This lowers to annotation pairs between the `defn` name and parameter vector.
Unknown attributes are preserved because Coil annotation keys are open.

### Structs and sum types

```rust
struct Point {
    x: i64,
    y: i64,
}

enum Shape {
    Empty,
    Circle { radius: f64 },
    Rect { width: i64, height: i64 },
}

let p = Point { x: 10, y: 20 };
let s = Shape::Rect { width: 10, height: 20 };
```

These lower to `defstruct`, `defsum`, and named Coil constructors. The canonical
renderer always includes field names and preserves source evaluation order.

### Traits and implementations

```rust
trait Show<Self> {
    fn show(x: Self) -> i64;
}

impl Show for Point {
    fn show(p: Point) -> i64 { p.x + p.y }
}

impl<T: Eq> Eq for Box<T> {
    fn eq(a: Box<T>, b: Box<T>) -> bool { a.value == b.value }
}

impl Point {
    fn origin() -> Point { Point { x: 0, y: 0 } }
    fn sum(p: Point) -> i64 { p.x + p.y }
}
```

These lower to `deftrait`, trait `impl`, generic `impl`, and inherent `impl`.
Receiver dispatch remains Coil's: `sum(p)` is an ordinary call whose owner is
inferred from argument zero, and associated calls are `Point::origin()`.
`p.sum()` is deliberately not syntax in version 1 because it would obscure this
distinction and collide with field access.

Derives use `#[derive(...)]` on a struct or enum and lower to a following native
`derive` form. Configured derives use expression syntax:

```rust
#[derive(Serialize(rename_all(:camelCase)), Deserialize(rename_all(:camelCase)))]
struct User { user_id: i64 }
```

### Foreign declarations and generated declarations

```rust
extern "c" {
    fn write(fd: i64, data: ptr<i8>, len: i64) -> i64;
    fn printf(format: ptr<i8>, ...) -> i32;
}

cimport "sys/ioctl.h" { ioctl };
export_c { run as "run" };
```

These lower to `extern`, `cimport`, and `export-c`. An `extern` item may carry
`#[header("...")]`. Calling conventions other than `c` are accepted as string or
identifier values and emitted as their native keyword/value.

Metaprogram declarations whose surface is too specialized (`defannotation`,
`defderive`, `register-derive`, reader-provider registration) initially use the
native escape. They remain fully representable and may gain dedicated sugar
without changing the language's completeness.

## Bindings, places, and assignment

```rust
let x = expression;
let mut y = expression;
let mut alias = mut y;       // aliases y's place
let mut copy = load(y);      // fresh cell containing y's current value

y = expression;             // (store! y expression)
*pointer = expression;       // (store! pointer expression)
let value = *pointer;        // (load pointer)
object.field = value;        // (set! (.field object) value)
let value = object.field;    // (.field object)
```

`mut place` is a prefix expression lowering to `(mut place)` and `load(place)` is
ordinary call syntax. Canonical output uses `load(place)` when a native `(load
place)` must remain explicit. `=` is assignment; equality is `==`, lowering to
Coil `=`. Compound assignments lower without inventing primitive semantics:

```rust
x += y;  // (store! x (+ (load x) y))
x -= y;  // analogous; also *=, /=, %=, &=, |=, ^=, <<=, >>=
```

Compound assignment currently requires a simple named place such as `x`. Use an
explicit `load`/`store!` sequence (or `coil`) for projected places whose address
must be evaluated exactly once.

Indexing and fields are surface sugar:

```rust
p.field             // (.field p)
p[index]             // (get p index), trait-level indexing
place(p, index)      // explicit project/library place operation
```

Low-level `primitive::index`, `field`, `load`, and `store!` remain available as
ordinary calls or through `coil`.

## Expressions and operators

Calls, constructors, literals, and blocks are expressions. Array literals use
`[a, b, c]`. There is no tuple literal because Coil has no tuple type.

```rust
f(a, b)
Type::<T>::associated(x)
generic::<T, U>(x)
if condition { then_value } else { else_value }
```

Operator lowering is purely syntactic:

| CoilRS | Coil |
|---|---|
| `a + b`, `a - b`, `a * b`, `a / b`, `a % b` | `(+ a b)`, `(- a b)`, etc. |
| `a == b`, `a != b`, `a < b`, `a <= b`, `a > b`, `a >= b` | `(= a b)`, `(!= a b)`, etc. |
| `a & b`, `a \| b`, `a ^ b`, `a << b`, `a >> b` | `(& a b)`, `(\| a b)`, etc. |
| `a && b`, `a \|\| b`, `!a` | `(and a b)`, `(or a b)`, `(not a)` |
| `-a` | `(- 0 a)` in canonical v1 |

Precedence follows Rust for the operators above. Operators still resolve to
Coil's traits or forms; the reader performs no type-directed selection. Metal
operations such as `primitive::iadd` are ordinary qualified calls.

Explicit type application is `callee::<T, U>(args...)` and lowers to Coil's
generic call shape `(callee [T U] args...)`. A type argument list in a non-call
position is a type, not an expression.

Coil keywords are named arguments rather than Rust fields when they occur in an
ordinary call:

```rust
configure(:mode, :fast)      // (configure :mode :fast)
```

## Control flow

All control constructs are expressions and preserve Coil's result typing.

```rust
if test { a } else { b }

match value {
    Some { value } => value,
    None => 0,
}

loop {
    if done { break result; }
    continue;
}

while condition { body; }
for i in 0..10 { body; }
```

`match` variant payloads lower to Coil's vector patterns. `_` remains `_`.
Named payload patterns are reserved for a later extension; v1 uses positional
brackets when field-name intent would be ambiguous:

```rust
match result {
    Ok[value] => value,
    Err[error] => handle(error),
}
```

The remaining core control forms are:

```rust
when condition { body; }
unless condition { body; }

cond {
    test1 => value1,
    test2 => value2,
    else => fallback,
}

case value {
    0 => zero,
    1 => one,
    else => fallback,
}

block :name {
    return_from :name, value;
}

try { expression }          // (try expression), not exception handling
```

`break;`, `break value;`, and `continue;` map directly. Coil has no general
`return`; CoilRS does not invent one. `return_from` maps to `return-from`.
Self-tail recursion remains the normal way to express early function structure
without a block.

## Compile-time and metaprogramming

```rust
let n = comptime { fact(5) };

meta {
    generate_declarations()
}

checker my_lint;
checker raw_depth before_expand;
transform my_lowering;
transform_once one_pass;
```

These lower to `comptime`, `meta`, `checker`, `transform`, and
`transform-once`. `before_expand` lowers to `:phase before-expand`.

Quote, unquote, and splice operate on Coil syntax rather than CoilRS syntax in
version 1. This is intentional: macro templates must preserve Coil's exact
hygiene and syntax-object model, and the native escape already provides it:

```rust
fn when_macro(c: Code, body: Code) -> Code {
    coil { `(if ~c (do ~@body) 0) }
}
```

Because a function with `Code` parameters and a `Code` result is already how Coil
defines a macro, no `macro` keyword is introduced. Reflection and `primitive::code_*`
operations are ordinary functions.

Registration forms and arbitrary generated top-level forms are always available
through `coil`:

```rust
coil {
    (reader-provider "my.reader" read-mine)
    (defannotation :http/route Route)
}
```

## Tests and documentation

```rust
/// Returns the sum of two values.
fn add(x: i64, y: i64) -> i64 { x + y }

#[test]
fn addition() -> i64 {
    assert-eq(add(20, 22), 42);
    0
}

```

`#[test] fn` lowers to `deftest`. Named-suite membership is project configuration,
not a Coil source declaration, and remains in `Coil.toml` under `[test.suites.*]`.
Assertions and property-test vocabulary are ordinary calls and therefore need no
reader support.

## Native Coil escape

The escape is part of the core grammar, not a preprocessor:

```rust
coil { ONE_OR_MORE_NATIVE_COIL_FORMS }
```

At item or statement position, all enclosed native forms are spliced into the
surrounding sequence. In expression position, exactly one native form is required
and becomes that expression. The content is passed to Coil's built-in configurable
s-expression reader; it is not tokenized as CoilRS first. Native strings, C
strings, characters, comments, quote/unquote/splice, vectors, and nested
parentheses therefore keep their ordinary meanings.

Braces delimiting an escape are recognized only outside native strings,
characters, and line comments. To avoid ambiguity, a top-level native `}` symbol
inside an escape must be written with an equivalent escaped spelling or placed in
a string. Canonical output never emits such an ambiguous bare symbol.

Two convenient single-form escapes are also defined:

```rust
let x = coil_expr { (some-new-macro a b) };
coil_item { (some-new-declaration Name ...) }
```

`coil_expr` requires exactly one form. `coil_item` is legal only where an item is
legal and may contain one or more forms. Bare `coil` infers the required mode from
its syntactic position.

Escaped forms may refer to bindings created by CoilRS because the reader parses
the complete source into one syntax context. The implementation must not parse
each escape in an unrelated hygiene context.

## Canonical conversion and round-trip policy

The project should expose both directions:

```sh
coil run input.coilrs --use experiments.coilrs.lang
coil run experiments.coilrs.lang input.coilrs > output.coil
coilrs from-coil input.coil > output.coilrs
coilrs to-coil input.coilrs > output.coil
```

The repository implementation is currently invoked directly:

```sh
python3 src/dialects/rust/coilrs.py from-coil input.coil \
  --structured-pretty > output.coilrs
python3 src/dialects/rust/coilrs.py to-coil input.coilrs > output.coil
python3 src/dialects/rust/coilrs.py from-coil-tree COIL_CHECKOUT CONVERTED \
  --install-reader --structured-pretty
cd CONVERTED
coil build src/compiler/main_a64.coilrs --use experiments.rust.lang -o coilrs-compiler
```

Tree conversion writes `.coilrs` sources and small `.coil` namespace-index
stubs. The one entry reader invocation materializes all adjacent `.coilrs`
modules into ordinary Coil before the loader follows imports. This is necessary
because Coil reader providers replace the entry read; textual imports otherwise
retain the default reader. Materialization uses atomic replacement and is
confined to the explicitly converted copy.

`from-coil` without `--structured-pretty` is the byte-exact archival mode: it
wraps the complete source in one `coil` escape. `--pretty` structures the module
declaration and retains one fallback body. `--structured-pretty` is the normal
canonical conversion: it renders every form whose exact tree round trip it can
prove and falls back per form otherwise.

The exact CLI packaging may differ, but the following behavior is required:

- The reader accepts every construct documented above.
- `to-coil` prints ordinary Coil accepted by the default reader.
- `from-coil` uses dedicated CoilRS syntax only when it can reproduce the exact
  native form shape; otherwise it emits `coil_item` or `coil_expr`.
- Reading canonical CoilRS and printing it again is idempotent.
- Native Coil -> canonical CoilRS -> native Coil preserves parsed `Code` modulo
  source locations and hygiene metadata that cannot originate in source text.
- CoilRS -> native Coil -> canonical CoilRS preserves semantics and becomes stable
  after the first canonicalization.
- Comments are best-effort in the source converter. Doc comments attached to
  declarations must be preserved; arbitrary comments are not part of `Code` and
  require a token-preserving conversion path if exact retention is desired.

The first test corpus should include one example for every section in this file,
then run the converter over the repository's ordinary `.coil` programs. Any form
the pretty surface cannot yet express must still pass via an escape; unsupported
syntax is never grounds for a failed conversion.

## Deliberate non-features

- No ownership, moves, lifetimes, borrow checker, or automatic destructors.
- No implicit dereference, autoref, method-call syntax, or overloaded field/index
  assignment beyond the explicit lowerings above.
- No implicit final `return`; a block simply yields its last expression as Coil
  `do` does.
- No Rust tuple, reference, closure, async, or `?` semantics unless a future Coil
  library/dialect defines them and the syntax lowers transparently to that API.
- No attempt to reserve all future Coil forms. Native escape is the compatibility
  boundary.

Those omissions keep CoilRS honest: it is readable Rust-like notation for Coil's
actual semantics, with an exact route back to Coil whenever surface sugar would
hide or distort them.
