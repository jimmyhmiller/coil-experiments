# Frontend grammar DSL

The entire currently implemented JavaScript/JSX grammar surface is the single
`def-frontend-grammar` form in `frontend_spec.coil`. That is the file to read or
edit when changing language syntax.

The sections have these roles:

- `terminals` gives source bytes stable symbolic names.
- `events` names the packed scanner event kinds consumed by grammar dispatch.
- `operators` groups named one-byte terminals or one-to-three-byte string
  lexemes by associativity and precedence. It generates longest-match width,
  precedence, combined-info, and lookahead queries.
- The two `forms` sections select primary and postfix parser forms from an event
  kind or named terminal.
- `productions` describes ordered grammar atoms. Supported atoms are `terminal`,
  `keyword`, `rule`, `repeat`, and `separated`.

At Coil compile time, `grammar.coil` validates the specification and produces:

- symbolic terminal, parser-form, and production identifiers;
- an inlined terminal-byte query;
- a straight-line precedence dispatch;
- primary and postfix dispatch functions;
- specialized terminal and keyword accessors for every production;
- generic production introspection queries used by DSL contract tests.

The parser backend consumes the generated accessors. Terminal bytes and keyword
spellings for supported grammar productions do not appear in `parser.coil`.

## Semantic parser generator

`parser_generator.coil` is the second compile-time layer. Its final, deliberately
data-only section is the semantic parser specification. The first migrated form
is:

```lisp
(separated-value array-expression
  (open (syntax/array-production-terminal 0))
  (separator (syntax/array-production-terminal 1))
  (close (syntax/array-production-terminal 2))
  (element-precedence 0)
  (emit-op ir/OP-JS-ARRAY))
```

The metaprogram validates that form and generates the complete repetition,
separator, error propagation, scratch lifetime, span construction, and direct
IR-emission control flow as `parse-array-generated!`. The old handwritten
`parse-array!` no longer exists. Nested-array tests exercise the generated path.

The generated code targets a narrow zero-cost backend ABI supplied at the macro
call site: cursor position/current byte/advance/consume, diagnostic failure,
expression recursion, scratch push, and list-operation emission. Language
productions do not contain arbitrary Coil parsing code.

`separated-value` is the first vertical slice, not the intended endpoint. Next
generator forms must cover sequences, choices, bindings, optional/repeat,
mode transitions, predicates, semantic metadata, regions, and CFG actions.
Handwritten productions are migrated only by adding such generator capability
and then deleting their old parser function.

For now compiler and semantic specification share `parser_generator.coil`.
Coil expands an imported `Code -> Code` helper as a nested macro before its
caller can supply runtime Code values, so splitting them cleanly requires a
compile-time-library linkage feature. The specification is isolated at the end
of the file pending that compiler improvement.
