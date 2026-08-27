// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-recover-source-order-differential.mjs PINNED_OHM_REPOSITORY');
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));
const {recoverSourceOrder} = await import(
  path.join(upstream, 'packages/ohm-js/extras/recoverSourceOrder.js')
);

const grammar = ohm.grammar(String.raw`G {
  test1 = (a b)+ c*
  test2 = (a b)? c? "."
  test3 = ((a b)* c)+
  test4 = (c? (a b*)+)*
  a = "a"
  b = "b"
  c = "c"
}`);
const semantics = grammar.createSemantics().addOperation('signature', {
  _default(...children) {
    return recoverSourceOrder(children)
      .map(child => `${child.ctorName}[${child.source.startIdx}..${child.source.endIdx}]`)
      .join(' ');
  },
});
const cases = [
  ['test1', 'abc', 'test1'],
  ['test2-empty', '.', 'test2'],
  ['test2-full', 'ab.', 'test2'],
  ['test3', 'ababcabc', 'test3'],
  ['test4', 'abbabab', 'test4'],
];
const expected = `${cases
  .map(([label, input, rule]) => `${label}|${semantics(grammar.match(input, rule)).signature()}`)
  .join('\n')}\n`;
const coil = spawnSync(
  'coil',
  [
    'run',
    'tests/ohm/recover-source-order-dump-runtime.coil',
    '--use',
    'experiments.ohm.builder-lang',
    '--backend',
    'arm64',
  ],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared ${cases.length}; exact ${exact ? cases.length : 0}; different ${exact ? 0 : cases.length}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${expected}\nACTUAL:\n${actual}\n`);
  process.exitCode = 1;
}
