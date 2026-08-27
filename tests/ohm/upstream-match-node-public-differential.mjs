// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-match-node-public-differential.mjs PINNED_OHM_REPOSITORY');
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));

const grammar = ohm.grammar(`G {
  Start = item+ ending?
  item = letter | digit
  ending = "!"
}`);
const hex = value => Buffer.from(value, 'utf8').toString('hex');
const semantics = grammar.createSemantics().addOperation('nodeSignature', {
  _default(...children) {
    const flags = `${this.isTerminal() ? 't' : '-'}${this.isIteration() ? 'i' : '-'}${this.isOptional() ? 'o' : '-'}`;
    return `(${hex(this.ctorName)}:${this.source.startIdx}:${this.source.endIdx}:` +
      `${hex(this.sourceString)}:${flags}:${this.numChildren}` +
      `${children.map(child => `,${child.nodeSignature()}`).join('')})`;
  },
});

const lines = [];
for (const [label, input] of [['absent', 'a2'], ['present', 'a2!']]) {
  const result = grammar.match(input);
  lines.push(
    `${label}|${result.input}|${result.succeeded() ? 1 : 0}|${result.failed() ? 1 : 0}|` +
      `${result.toString()}|${result.matcher.getInput()}|${result.matcher.grammar.name}|` +
      semantics(result).nodeSignature()
  );
}
for (const [label, input] of [['unicode-failure', 'a😀'], ['initial-failure', '!']]) {
  const result = grammar.match(input);
  const interval = result.getInterval();
  lines.push(
    `${label}|${hex(result.input)}|0|1|${result.getRightmostFailurePosition()}|` +
      `${hex(result.getExpectedText())}|${hex(result.shortMessage)}|${hex(result.message)}|` +
      `${hex(result.toString())}|${interval.startIdx}|${interval.endIdx}`
  );
}
const expected = `${lines.join('\n')}\n`;
const coil = spawnSync(
  'coil',
  [
    'run',
    'tests/ohm/match-node-public-dump-runtime.coil',
    '--use',
    'experiments.ohm.builder-lang',
    '--backend',
    'arm64',
  ],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared 4; exact ${exact ? 4 : 0}; different ${exact ? 0 : 4}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${expected}\nACTUAL:\n${actual}\n`);
  process.exitCode = 1;
}
