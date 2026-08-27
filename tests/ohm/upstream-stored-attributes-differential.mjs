// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-stored-attributes-differential.mjs PINNED_OHM_REPOSITORY');
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));
const {addStoredAttribute} = await import(
  path.join(upstream, 'packages/ohm-js/extras/storedAttributes.js')
);

const grammar = ohm.grammar(`Arithmetic {
  Exp = AddExp
  AddExp = AddExp "+" number  -- plus
         | AddExp "-" number  -- minus
         | number
  number = digit+
}`);
const semantics = grammar.createSemantics();
const exp = semantics(grammar.match('3 + 4 - 1'));
addStoredAttribute(semantics, 'polarity', 'initPolarity(pol)', setPolarity => ({
  AddExp_plus(left, _operator, right) {
    setPolarity(this, '+');
    left.initPolarity(this.polarity);
    right.initPolarity(this.polarity);
  },
  AddExp_minus(left, _operator, right) {
    setPolarity(this, '-');
    left.initPolarity(this.polarity);
    right.initPolarity(this.polarity);
  },
  _default(...children) {
    setPolarity(this, this.args.pol);
    children.forEach(child => child.initPolarity(this.args.pol));
  },
}));
exp.initPolarity('=');
const values = [
  exp.polarity,
  exp.child(0).polarity,
  exp.child(0).child(0).polarity,
  exp.child(0).child(0).child(0).polarity,
  exp.child(0).child(0).child(0).child(0).polarity,
];
const ranks = {'=': 0, '-': 1, '+': 2};
let missing = 'initialized';
try {
  void exp.child(0).child(0).child(1).polarity;
} catch (error) {
  if (error.message === "Attribute 'polarity' not initialized") missing = 'none';
}
const expected = `${values.map(value => `${value}${ranks[value]}`).join('|')}|${missing}\n`;
const coil = spawnSync(
  'coil',
  [
    'run',
    'tests/ohm/generic-stored-attributes-runtime.coil',
    '--use',
    'experiments.ohm.builder-lang',
    '--backend',
    'arm64',
  ],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared 6; exact ${exact ? 6 : 0}; different ${exact ? 0 : 6}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${expected}\nACTUAL:\n${actual}\n`);
  process.exitCode = 1;
}
