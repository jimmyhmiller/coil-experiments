# CoilRS language reference

CoilRS is a reader syntax for Coil. The reader turns CoilRS text into the same
`Code` trees that the native Coil reader produces. Macros, checkers, transforms,
type checking, and code generation run after that conversion.

The reader has no native-source escape and no AST serialization syntax. The
converter emits CoilRS for each native list, vector, and atom. It uses an
escaped macro call for a form that has no dedicated spelling.

## Current status and limitations

The Coil-native reader, converter, fixtures, and exact syntax-tree audits pass.
The full-checkout audit currently converts 634 valid `.coil` sources and copies
23 explicitly listed malformed diagnostic fixtures as data. The converted
`src/compiler/main_a64.coilrs` builds a compiler, that compiler runs, and its
version output identifies the converted checkout's `src/stdlib` directory. The
monitored end-to-end gate most recently peaked at 4.097 GiB of aggregate RSS.

This is not yet a completely self-hosting, native-free checkout:

- The tree converter emits a `.coilrs` file plus a native `.coil` loader stub
  for each converted module. The stub passes the CoilRS text to
  `rust-like-items`, so imported modules still enter through native loader files.
- The generated compiler can run, but asking it to compile another CoilRS file
  against the converted checkout currently exposes a bootstrap cycle: loading
  the converted prelude needs the Rust-like reader, while compiling that reader
  needs the prelude.
- Generated CoilRS is structurally exact and substantially more readable than
  AST constructors, but compiler code remains mechanical in places, with
  low-level primitive calls, explicit `do` blocks, and open-ended macro calls.
- Structural CoilRS-to-Coil restoration is tested through the reader, but there
  is not yet a polished command that pretty-prints the restored tree as native
  Coil source.

Accordingly, the reader and exact round-trip representation are usable, and the
compiler conversion is a working build demonstration, but the larger
native-stub-free/self-hosting goal remains unfinished.

## Complete program

```rust
module example::points;

use coil::io::{stdout, print-int, print-str};

struct Point {
    x: i64,
    y: i64,
}

fn sum(p: Point) -> i64 {
    p.x + p.y
}

fn main() -> i64 {
    let mut total = 0;
    let p = Point { x: 19, y: 23 };
    total = sum(p);
    print-int(stdout(), *total);
    print-str(stdout(), "\n");
    0
}
```

`tests/rust/complete.coilrs` and `tests/rust/structured.coilrs` execute this
set of constructs.

## Names and paths

Coil names may contain `-`, `?`, and a trailing `!`:

```rust
empty-list?()
al-push!(mut values, value)
primitive::alloc-stack(i64)
```

`::` maps to `/` in a Coil symbol. A module declaration maps `::` to `.`.
Backticks quote names that conflict with CoilRS grammar or contain other
characters:

```rust
`match`(value, arms)
`free-identifier=?`(left, right)
:build::id
:`free-identifier=?`
```

The converter only adds backticks when the grammar requires them.

## Literals

CoilRS accepts Coil integers and floats, booleans, strings, C strings,
characters, keywords, and vectors:

```rust
0
-9223372036854775808
3.5
true
"text\n"
c"bytes\0"
'x'
'\n'
:ready
[1, 2, 3]
```

Comments use `//` and `/* ... */`. Delimiters inside strings and comments do
not end the surrounding construct.

## Types

Type application uses angle brackets. A type vector uses square brackets.

```rust
i64
ptr<i64>
mut<ArrayList<u8>>
slice<u8>
dyn<Allocator>
Result<i64, Error>
[i64, bool]
fnptr<c, [i64], i64>
```

## Modules and imports

```rust
module my::program;

use coil::io::*;
use coil::io::{stdout, print-int};
use coil::alloc as alloc;
use coil::str::* except { sb-new };
pub use coil::slice::{slice-len as len};
```

The converter uses an order-preserving form when a native import contains an
option order that the compact syntax cannot express:

```rust
use "coil.alloc" with {
    as: alloc,
    use: *,
};
```

The `with` fields are `as`, `use`, `exclude`, `rename`, and `reexport`. Their
order becomes the option order in the native `import` form.

## Declarations

Constants, aliases, structs, and sums use these forms:

```rust
const LIMIT: i64 = 10;
alias Field = primitive::field;

struct Pair<T> {
    left: T,
    right: T,
}

enum Option<T> {
    Some { value: T },
    None,
}
```

Functions support generic bounds, parameter packs, attributes, and more than
one body form:

```rust
#[inline(Always)]
fn identity<T: Copy + Eq>(value: T) -> T {
    trace(value);
    value
}

fn consume<Args...>(args...: Args...) -> i64 { 0 }
```

Traits, trait implementations, and inherent implementations share the function
syntax:

```rust
trait Show<Self> {
    fn show(value: Self) -> i64;
}

impl Show for Widget {
    fn show(value: Widget) -> i64 { value.code }
}

impl Widget {
    fn code(value: Widget) -> i64 { value.code }
}
```

`derive` and other annotations use attributes:

```rust
#[derive(Eq, Hash)]
struct Key { value: i64 }

#[http::route(Get("/users"))]
fn users() -> i64 { 0 }
```

## Foreign declarations and exports

```rust
extern "c" {
    fn puts(text: ptr<i8>) -> i32;
    fn printf(format: ptr<i8>, ...) -> i32;
}

cimport "stdio.h" { printf };
export { main, helper };
export_c { main as "entry" };
```

## Bindings, places, and assignment

`let` creates immutable or mutable stack bindings. `*` loads a pointer. A plain
field access lowers to a Coil accessor. Assignment selects `set!` for an
accessor and `store!` for a loaded pointer place.

```rust
let value = 1;
let mut total = 0;
let element = values[index];
let field_value = record.field;
*pointer = value;
record.field = value;
total += value;
total -= value;
total *= value;
total /= value;
```

The converter keeps low-level place operations visible when their tree differs
from an accessor, for example `field(record, name)` and `set!(place, value)`.
These are ordinary Coil macro calls, not native-source or AST escapes.

## Calls and construction

```rust
f(a, b)
f::<T, U>(a, b)
Point { x: 1, y: 2 }
Maybe::Some { value: 42 }
(function_factory())(argument)
```

The generic-call spelling lowers to a call whose first argument is a native
type vector. Named construction lowers to alternating keyword/value arguments.

## Operators

CoilRS implements precedence for unary, arithmetic, shift, comparison,
equality, bitwise, and Boolean operators:

```rust
!flag
-value
*pointer
left * right + extra
value << 2
left < right && ready
bits & mask | extra
```

Parentheses override precedence.

## Conditions and blocks

```rust
if condition { yes() } else { no() }
when condition { action(); 0 }
unless condition { action(); 0 }

{
    let value = compute();
    use_value(value)
}
```

Semicolons separate sibling forms. The final expression supplies the block
value.

## Loops and exits

```rust
loop { break; }
while condition { step(); }
for i in 0..count { visit(i); }
loop { break 42; }
loop { break :outer, 42; }
while condition { continue; }

block :done {
    return_from :done, result;
    fallback
}
```

## Pattern and clause forms

```rust
match value {
    Some[x] => use_value(x),
    None[] => 0,
}

cond {
    first => one(),
    else => zero(),
}

case value {
    1 => one(),
    else => zero(),
}
```

A match arm may use a block with several forms. The converter uses an escaped
macro call for a malformed match tree that lacks its binding vector, preserving
that tree for compiler diagnostic fixtures.

## Compile-time and metaprogram forms

```rust
let answer = comptime { 40 + 2 };
try { operation() }
meta { generate() }
quote(value)
quasiquote(template(unquote(value), splice(rest)))
```

`unquote(value)` and `splice(value)` may also appear as standalone forms when a
macro needs those exact trees.

## Reader pipeline registrations

```rust
checker validate;
checker early before_expand;
transform lower;
transform_once normalize;
```

`before_expand` lowers to the native `:phase before-expand` option.

## Open-ended forms

Coil macros can introduce new list shapes without changing this reader. Use a
normal macro call in expression position or prefix a top-level form with
`item`:

```rust
custom-form!(value, option)
item defprimitive(code-count, :code-count);
```

If the macro name conflicts with CoilRS syntax, escape the name:

```rust
item `match`(value, arm);
```

## Conversion and round trips

Convert one native source by loading the converter reader provider:

```sh
coil run program.coil --use experiments.rust-like.convert > program.coilrs
```

Read or build CoilRS through the Rust-like provider:

```sh
coil run program.coilrs --use experiments.rust-like.lang
coil build program.coilrs --use experiments.rust-like.lang -o program
```

Convert a checkout into a separate directory:

```sh
coil run experiments.rust-like.tree -- /path/to/coil /tmp/coil-rust-like
```

The tree converter writes `.coilrs` files, native loader stubs, and the
`rust-like` reader package. It also writes a root `Coil.toml`. Build the compiler
inside that checkout at the path the compiler recognizes as a checkout build:

```sh
cd /tmp/coil-rust-like
mkdir -p build/bin
coil build src/compiler/main_a64.coilrs \
    --use experiments.rust-like.lang \
    -o build/bin/coil
build/bin/coil --version
```

The version output reports `stdlib: checkout: .../src/stdlib`. The compiler then
loads the converted checkout's standard library. The command
`scripts/rust-like-test.sh --compiler-copy ../coil` checks exact `Code` equality
across the checkout and runs this compiler gate.

## Implementation files

- `reader.coil` parses CoilRS into `Code`.
- `converter.coil` converts native Coil text to CoilRS.
- `tree.coil` converts directory trees and installs the reader package.
- `rust.coil` registers `experiments.rust-like.lang`.
- `convert.coil` registers `experiments.rust-like.convert`.
