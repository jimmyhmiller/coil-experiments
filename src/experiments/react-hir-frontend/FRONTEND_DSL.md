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
The recursive-control and HIR-building algorithms remain backend code; the DSL
does not yet generate complete recursive parser function bodies.
