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

`parser_generator.coil` is the second compile-time layer. Its final,
deliberately data-only section specifies every direct-parser production. The
specification contains production kinds and semantic parameters, not arbitrary
Coil function bodies. Generator algorithms currently include:

- `word-value` and `quoted-value` for leaf values;
- `separated-value`, `named-value`, `postfix-name`, and
  `postfix-separated` for aggregates and postfix forms;
- `primary-dispatch`, `postfix-chain`, and `precedence-expression` for
  expression dispatch, Pratt recursion, conditionals, and assignment;
- `terminated-expression`, `binding-declaration`, `statement-dispatch`, and
  `scoped-repeat` for statements and lexical blocks;
- `conditional-statement` and `loop-statement` for explicit CFG construction;
- `labeled-statement` and `control-transfer` for source-named labels, lazy
  labeled-break exits, loop-specific continue targets, duplicate detection,
  restricted-production line breaks, and function-boundary isolation;
- `try-statement` for structured try/catch/finally operations with owned
  regions, catch scopes, and explicit region-yield terminators;
- `arrow-lookahead` and `arrow-expression` for balanced TypeScript-aware
  disambiguation and synchronous or async arrow regions;
- `function-declaration` for nested regions, scopes, parameters, captures, and
  implicit returns;
- `program-root` for root storage initialization, repetition, fallthrough, and
  IR membership finalization;
- `structured-type-parser`, `structured-type-span`,
  `structured-type-parameters`, and `structured-type-arguments` for generated
  TypeScript type trees. The precedence ladder currently emits primary,
  postfix, intersection, union, and conditional types, including mapped types,
  `infer`, `keyof`/`readonly`/`unique`, type-level `typeof`, and typed or
  untyped property signatures with ordinary, quoted, numeric, or computed names.
  Union and intersection nodes preserve an optional leading `|` or `&`, even
  for the TypeScript-valid single-member form.
  Call, construct, method, and getter signatures retain whether a return type
  was written, while function and constructor type expressions require one;
- `type-binding-pattern` for structured object, array, rest, assignment, and
  elision patterns in function, constructor, and method type parameters,
  including quoted, numeric, and computed object keys;
- `erased-declaration` for type-alias declaration ownership;
- `structured-interface` for interface type parameters, heritage, and the
  structured type-literal body;
- `structured-module` for internal modules, namespaces, dotted namespace
  chains, quoted external modules, and global augmentations, with every body
  represented by an owned region and lexical scope;
- `enum-declaration` for ordinary, const, and ambient enums with structured
  members, exact name forms, and optional initializer operands;
- `statement-terminator` for explicit semicolons and JavaScript ASI boundaries;
- `import-declaration` for side-effect, default, namespace, named, aliased, and
  type-only imports, creating runtime bindings only for value imports.

The macro call in `direct_parser.coil` supplies named backend roles. These roles
are primitive cursor/source queries, diagnostics, scratch storage, binding and
capture support, and IR-builder operations. Role lookup happens at compile time;
generated parsers are ordinary statically compiled Coil functions with no
runtime interpreter or production tables.

No handwritten `parse-*` definition remains in `direct_parser.coil`.
`benchmarks/check-generated-direct-parser.sh` enforces both halves of that
contract: the runtime source must contain none, while macro expansion must
contain all 77 expected generated definitions, including labeled statements,
their control-transfer resolution, prefix type
assertions, their JSX-disambiguating lookahead, and structured enums.
The module-statement production also owns import-equals, export assignment,
and namespace-export declarations.

Language-coverage changes additionally run through `react-hir-check`, which
executes the generated parser and the complete IR verifier for one source file.
`benchmarks/check-react-hir-syntax-fixtures.sh` runs the permanent focused
syntax fixtures through that full path.
`run-typescript-coverage.sh` uses Oxc only as a validity filter for the external
TypeScript/TSX corpus, then reports whole-file and byte-weighted Coil coverage.
Those corpus measurements are tracked separately from syntax-feature coverage;
opaque acceptance does not count as structured language support.

`benchmarks/check-typescript-generated-core.sh` permanently covers the first
TypeScript slice: directives, every import-clause shape, type-only imports,
generic type aliases, annotations, generic functions, bitwise and shift
operators, compound assignments, unary `~`, and ASI. Passing means the emitted
IR also passes the complete verifier.

`direct_parser_test.coil` registers every structural check as a `deftest`, so
the project suite executes its IR-shape and deliberate-corruption assertions.

`benchmarks/check-typescript-type-oracle.sh` supplies the independent type-tree
oracle. Canonical snippets are parsed by local Oxc and by Coil's generated
parser; an exhaustive Oxc visitor normalizes the intentional difference that
Coil materializes entity-name leaves as SSA values, then compares the ordered
type/signature node shape. It covers every non-JSDoc `TSType` and every
`TSSignature` variant, compares Oxc source spans, and pins operand/immediate
schemas for modifier-rich forms. It is part of the generated-core gate.

For now compiler and semantic specification share `parser_generator.coil`.
Coil expands an imported `Code -> Code` helper as a nested macro before its
caller can supply runtime Code values, so splitting them cleanly requires a
compile-time-library linkage feature. The specification is isolated at the end
of the file pending that compiler improvement.
