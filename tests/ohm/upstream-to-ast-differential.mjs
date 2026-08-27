// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-to-ast-differential.mjs PINNED_OHM_REPOSITORY');
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));
const {semanticsForToAST, toAST} = await import(
  path.join(upstream, 'packages/ohm-js/extras/semantics-toAST.js')
);

const grammar = ohm.grammar(`G {
  Start = AddExp
  AddExp = AddExp_plus | AddExp_minus | PriExp
  AddExp_plus = AddExp "+" PriExp
  AddExp_minus = AddExp "-" PriExp
  PriExp = PriExp_paren | number
  PriExp_paren = "(" Start ")"
  number = digit+
  Mix = a? b* "|" a? b*
  a = "a"
  b = "b"
  LexList = listOf<digit, "+">
  SynList = ListOf<digit, "+">
}`);

const hex = value => Buffer.from(value, 'utf8').toString('hex');
function signature(value) {
  if (value === null) return 'n';
  if (typeof value === 'string') return `s${hex(value)}`;
  if (typeof value === 'boolean') return value ? 'b1' : 'b0';
  if (typeof value === 'number') return `d${value}`;
  if (Array.isArray(value)) return `a[${value.map(signature).join(',')}]`;
  return `o{${Object.keys(value)
    .sort()
    .map(key => `${hex(key)}=${signature(value[key])}`)
    .join(',')}}`;
}

const short = grammar.match('10 + 20');
const long = grammar.match('10 + 20 - 30');
const optional = grammar.match('a|bb', 'Mix');
const list = grammar.match('3+5', 'LexList');
const emptyList = grammar.match('', 'LexList');
const syntacticList = grammar.match('3 + 5', 'SynList');
const syntacticEmpty = grammar.match('', 'SynList');
const outputs = [];
const emit = (label, value) => outputs.push(`${label}|${signature(value)}`);

emit('default', toAST(short));
emit('optional', toAST(optional, {}));
emit('renamed', toAST(short, {AddExp_plus: {expr1: 0, expr2: 2}}));
emit('operator', toAST(short, {AddExp_plus: {expr1: 0, op: 1, expr2: 2}}));
emit('removed', toAST(short, {AddExp_plus: {0: 0}}));
emit('no-type', toAST(short, {AddExp_plus: {0: 0, type: undefined}}));
emit('static', toAST(short, {AddExp_plus: {expr1: 0, op: 'plus', expr2: 2}}));
emit(
  'boxed',
  toAST(short, {AddExp_plus: {expr1: Object(0), op: 'plus', expr2: Object(2)}})
);
emit(
  'computed-property',
  toAST(short, {
    AddExp_plus: {
      expr1: 0,
      expr2: 2,
      str(children) {
        return children.map(child => child.toAST(this.args.mapping)).join('');
      },
    },
  })
);
emit('forward', toAST(long, {AddExp_plus: 2}));
emit(
  'action',
  toAST(long, {
    AddExp_plus(expr1, _op, expr2) {
      return `plus(${expr1.toAST(this.args.mapping)}, ${expr2.toAST(this.args.mapping)})`;
    },
  })
);
emit('reintroduced', toAST(long, {Start: {type: 'Start', 0: 0}}));
emit(
  'combo',
  toAST(long, {
    AddExp_plus: {augend: 0, addend: 2, type: 'AddExpression'},
    AddExp_minus: {minuend: 0, subtrahend: 2, type: 'SubExpression'},
  })
);
emit('list', toAST(list));
emit('list-empty', toAST(emptyList));
emit('syntactic-list', toAST(syntacticList));
emit('syntactic-empty', toAST(syntacticEmpty));
emit(
  'list-action',
  toAST(list, {nonemptyListOf(first, _separator, _rest) { return 'XX'; }})
);
emit('list-forward', toAST(list, {nonemptyListOf: 0}));
emit('empty-action', toAST(emptyList, {emptyListOf() { return 'nix'; }}));
const astSemantics = semanticsForToAST(grammar);
outputs.push(
  `semantics-meta|${Object.keys(astSemantics._getSemantics().operations).length}|toAST|1`
);
emit('semantics-apply', astSemantics(short).toAST({}));

const expected = `${outputs.join('\n')}\n`;
const coil = spawnSync(
  'coil',
  [
    'run',
    'tests/ohm/to-ast-public-dump-runtime.coil',
    '--use',
    'experiments.ohm.builder-lang',
    '--backend',
    'arm64',
  ],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const lines = outputs.length;
const exact = actual === expected;
process.stdout.write(`Compared ${lines}; exact ${exact ? lines : 0}; different ${exact ? 0 : lines}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${expected}\nACTUAL:\n${actual}\n`);
  process.exitCode = 1;
}
