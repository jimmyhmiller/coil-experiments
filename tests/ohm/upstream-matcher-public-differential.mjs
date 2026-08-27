// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-matcher-public-differential.mjs PINNED_OHM_REPOSITORY');
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));

const source = `G {
  basic = notLastLetter* letter
  notLastLetter = letter &letter
  tricky = tricky letter
         | lookaheadRule ""
         | "a" ""
  lookaheadRule = &"ac" "a"
}`;
const grammar = ohm.grammar(source);
const matcher = grammar.matcher();
const lines = [];

function hex(text) {
  return Buffer.from(text, 'utf8').toString('hex');
}
function cst(node) {
  const children = node.children.map(child => `,${cst(child)}`).join('');
  return `(${hex(node.ctorName)}:${node.source.startIdx}:${node.source.endIdx}:${hex(node.sourceString)}${children})`;
}
const semantics = grammar.createSemantics().addOperation('signature', {
  _nonterminal(...children) {
    return cst(this);
  },
  _terminal() {
    return cst(this);
  },
  _iter(...children) {
    return cst(this);
  },
});
function emit(label, result) {
  if (result.succeeded()) lines.push(`${label}|${matcher.getInput()}|ok|${semantics(result).signature()}`);
  else lines.push(`${label}|${matcher.getInput()}|fail|${result.getRightmostFailurePosition()}|${result.getExpectedText()}`);
}

matcher.replaceInputRange(0, 0, 'helloworld').replaceInputRange(3, 5, 'X');
emit('basic-1', matcher.match());
matcher.replaceInputRange(0, 4, '');
emit('basic-2', matcher.match('basic'));
matcher.replaceInputRange(3, 4, ' ');
emit('basic-3', matcher.match());
matcher.replaceInputRange(0, 4, 'aa');
emit('basic-4', matcher.match());
matcher.replaceInputRange(1, 2, '9');
emit('basic-5', matcher.match());
matcher.setInput('ab');
emit('tricky-1', matcher.match('tricky'));
matcher.replaceInputRange(1, 2, 'c');
emit('tricky-2', matcher.match('tricky'));

const expected = `${lines.join('\n')}\n`;
const coil = spawnSync(
  'coil',
  [
    'run',
    'tests/ohm/matcher-public-dump-runtime.coil',
    '--use',
    'experiments.ohm.builder-lang',
    '--backend',
    'arm64',
  ],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared 7; exact ${exact ? 7 : 0}; different ${exact ? 0 : 7}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${JSON.stringify(expected)}\nACTUAL:\n${JSON.stringify(actual)}\n`);
  process.exitCode = 1;
}
