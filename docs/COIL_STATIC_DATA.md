# Saying what is in a static — done

This was a report that Coil had no way to give a static its contents:
`primitive/alloc-static` allocated zeroed storage and took no initial value, so
the C frontend had to reproduce every initialised table with stores that ran
before `main`.

`(primitive/alloc-static TYPE INITIAL)` now exists, and this frontend uses it.
The report is kept here as the record of what was asked for and what it bought.

## What was asked for

Writable, type-aligned storage whose contents are in the binary — not a
read-only string literal, because Doom's dehacked support patches `states[]` and
`mobjinfo[]` at run time.

## What arrived

`(primitive/alloc-static TYPE INITIAL)` on the LLVM/object-file backend, taking
numeric constants, null pointers, C strings, structs, and arrays; narrow
aggregate fields laid out correctly; function-pointer relocations preserved;
runtime-dependent initialisers rejected rather than silently deferred. The
direct AArch64, x86-64, Wasm, and bytecode backends reject an initialised static
explicitly. The one-argument form is unchanged.

## What it bought

`src/dialects/c/emit.coil` folds every start-up store whose value is a constant
into the object's image, and defines the object holding it. The shape emitted is
the same storage type the frontend already used — a record is still a blob of
its alignment's unit, so nothing downstream had to change:

```lisp
(defn c_g_mobjinfo [] (-> (ptr (array (array i32 23) 137)))
  (primitive/alloc-static (array (array i32 23) 137) [[-1 149 100 150 ...] ...]))
```

A store whose value is an address — a string, another object, a function — has
no constant to fold into and stays a statement, so `states[].action` and
`sprnames[]` still run at start-up. That is a per-leaf decision, not a per-object
one: `states[]` keeps 448 stores out of the thousands it used to run.

Measured on Doom Generic, 81 translation units:

| | before | after |
| --- | --- | --- |
| start-up stores | 36,171 | 1,305 |
| `c_init_statics` share of the module | 44% | 4.5% |
| generated module | 6.6 MB | 4.1 MB |

The framebuffer hash is unchanged: `734a03fe31906bc3`, the same hash a
Clang-built Doom produces.

## What is still out of reach

An address is not a constant this compiler can write down, so an initialiser
holding one keeps its store. Reaching those would mean giving each eight-byte
slot of a blob its own type — a `defstruct` per record shape, with a `fnptr` or
`(ptr i8)` field where the relocation goes — rather than the uniform
`(array i64 N)` a record is lowered to today. It is possible; it is not obviously
worth a 4,835-field struct for `states[]`.
