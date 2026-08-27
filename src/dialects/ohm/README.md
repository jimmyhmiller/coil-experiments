# Ohm grammar metaprogram

This reader compiles an Ohm grammar into ordinary Coil parsing functions. Both
the grammar reader and the generated parser runtime are written in Coil. There
is no JavaScript, Python, subprocess, or runtime grammar interpreter.

The initial bootstrap supports the operators exercised by Ohm's canonical
`ohm-grammar.ohm`: sequence, ordered choice, `*`, `+`, `?`, negative and
positive lookahead, lexicalization, terminals, ranges, applications, inline
case labels, general parameterized-rule substitution, rule descriptions,
extension/override syntax, and the built-ins used there (`any`, `end`,
Unicode character classes, `caseInsensitive`, `applySyntactic`, `ListOf`, and
`NonemptyListOf`).

Run the end-to-end bootstrap gate through the reader provider with:

```sh
coil run tests/ohm/ohm-grammar.ohm --use experiments.ohm.lang
```

`--use` loads the Ohm metaprogram, which reads the grammar, emits ordinary Coil
parser functions, and compiles them. The generated parser then reads the
complete grammar source. Exit status zero means the self-parse succeeded.

Use `experiments.ohm.grammar` when mirroring `ohm.grammar()` exactly; it rejects
a second definition. Use `experiments.ohm.namespace` for the multi-grammar
`ohm.grammars()` model (including `// @namespace-import path`). The historical
`experiments.ohm.lang` provider remains convenient when a same-file inheritance
chain should directly expose its final grammar's parser functions.

The Coil-native programmatic `Builder`/`GrammarDecl` surface is also a reader
metaprogram. A normal Coil file can contain a top-level declaration such as:

```coil
(module example)

(build-ohm-grammar
  (grammars
    (grammar Base
      (define token [] (alt (terminal "a") (terminal "b"))))
    (grammar G (super Base)
      (withDefaultStartRule start)
      (override token [] (splice [(terminal "x")] [(terminal "y")]))
      (define start [] (seq (app token) (terminal "!"))))))

(defn main [] (-> i64)
  (if (parse "x!") 0 1))
```

Compile and run it with:

```sh
coil run example.coil --use experiments.ohm.builder-lang
```

The provider reads ordinary Coil, replaces `build-ohm-grammar` at read time,
and returns ordinary specialized Coil definitions. It supports declaration
chains, explicit supergrammars and default starts, `define`, `override`,
`extend`, ordered `splice`, all public v17 expression constructors, rule
formals, and descriptions. The declaration is not interpreted at runtime.

To inspect the generated Coil instead:

```sh
coil run experiments.ohm.lang tests/ohm/ohm-grammar.ohm > /tmp/ohm-generated.coil
coil check /tmp/ohm-generated.coil
```

Generated modules expose `parse-tree`, which returns an arena-backed CST match
result, `parse`, which returns a boolean while releasing that result, and
`grammar-object`, whose executable `superGrammar` chain reaches `BuiltInRules`
and `ProtoBuiltInRules`. See
`docs/ohm-conformance.md` for the current official-suite coverage and the exact
remaining compatibility work.

For differential auditing, `--use experiments.ohm.cst` prints an unambiguous
recursive CST signature for every successful fixture directive. Run the whole
corpus against the pinned upstream implementation with:

```sh
node tests/ohm/upstream-cst-differential.mjs /path/to/pinned/ohm
```

The current corpus has 243/243 exact structural matches with pinned Ohm 17.2.1, including
constructor names, child order, iteration wrappers, node source strings, and
absolute UTF-16 source intervals.

The public Interval/line-column projection is also checked directly:

```sh
node tests/ohm/upstream-interval-differential.mjs /path/to/pinned/ohm
```

Its 13/13 exact cases include UTF-16 offsets, CRLF and standalone-CR behavior,
and Ohm's `null`-versus-empty distinction for adjacent lines.

Public incremental Matcher states and the `extractExamples` extra have pinned
oracles as well:

```sh
node tests/ohm/upstream-matcher-public-differential.mjs /path/to/pinned/ohm
node tests/ohm/upstream-extract-examples-differential.mjs /path/to/pinned/ohm
```

They currently report 7/7 and 16/16 exact comparisons, respectively.

The recursive `toAST`/`semanticsForToAST` value oracle runs with:

```sh
node tests/ohm/upstream-to-ast-differential.mjs /path/to/pinned/ohm
```

It currently reports 22/22 exact comparisons.

VisitorFamily has a pinned behavioral oracle and a separate fully typed ABI:

```sh
node tests/ohm/upstream-visitor-family-differential.mjs /path/to/pinned/ohm
```

The oracle reports 8/8 exact comparisons. Typed visitor operations may accept
and return arbitrary Coil structs through `experiments.ohm.generic-visitor-family`.

The source-order and typed stored-attribute extras are pinned as well:

```sh
node tests/ohm/upstream-recover-source-order-differential.mjs /path/to/pinned/ohm
node tests/ohm/upstream-stored-attributes-differential.mjs /path/to/pinned/ohm
```

They currently report 5/5 and 6/6 exact comparisons. Generic stored attributes
accept arbitrary Coil values through `experiments.ohm.generic-stored-attributes`.

`--use experiments.ohm.trace` similarly executes the fixture's trace
directives and prints the complete trace tree. Its 13 translated upstream
cases are byte-for-byte identical to Ohm 17.2.1, including failed-branch
bindings, memo replay, sparse left-recursion children, and terminating
left-recursion entries.

Persistent semantics recipes use the same metaprogram workflow:

```sh
coil run semantics.recipe.json --use experiments.ohm.semantics-recipe
```

The generated module exposes `make-semantics`. Recipes embed the ordinary
grammar recipe and Coil-native action preambles/constructors, so reconstruction
compiles to normal Coil code and never evaluates JavaScript or shells out to
another language.
