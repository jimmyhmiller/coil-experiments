// Repository-development oracle only. Generated parsers never invoke Node.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) {
  throw new Error('usage: node upstream-grammar-differential.mjs PINNED_OHM_REPOSITORY');
}
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));

const source = `G1 {
  foo = bar
  bar = baz baz baz
  baz = qux
  qux = quux "123"
  quux = "42"
  aaa = "duh"
  bbb = ~aaa qux  -- blah
}
G2 <: G1 {
  qux := "100"
}`;
const namespace = ohm.grammars(source);
const expectedTemplates = [
  namespace.G1.toOperationActionDictionaryTemplate(),
  namespace.G2.toAttributeActionDictionaryTemplate(),
];

const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'coil-ohm-grammar-'));
const filenames = [path.join(temporaryDirectory, 'g1.ohm'), path.join(temporaryDirectory, 'g2.ohm')];
fs.writeFileSync(filenames[0], source.slice(0, source.indexOf('\nG2 <:')));
fs.writeFileSync(filenames[1], source);

let exact = 0;
const differences = [];
for (let index = 0; index < filenames.length; index++) {
  const coil = spawnSync(
    'coil',
    ['run', filenames[index], '--use', 'experiments.ohm.action-template-dump', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
  if (actual === expectedTemplates[index]) exact += 1;
  else differences.push({index, expected: expectedTemplates[index], actual});
}
fs.rmSync(temporaryDirectory, {recursive: true});

const defaultCases = [
  'G {}',
  'G { foo = "a" }',
  'G { digit += any }',
  'G { digit += any  blah = "3" }',
  'G { digit := any }',
  'G { digit := any  blah = "3" }',
  'G { x = "a"\n| -- nothing }',
];
for (let index = 0; index < defaultCases.length; index++) {
  const caseSource = defaultCases[index];
  const grammar = ohm.grammar(caseSource);
  const expected = [
    grammar.name,
    grammar.defaultStartRule ?? '',
    grammar.superGrammar.name,
    String(Object.keys(grammar.rules).length),
    grammar.isBuiltIn() ? '1' : '0',
    '',
  ].join('\n');
  const caseDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'coil-ohm-default-'));
  const filename = path.join(caseDirectory, `case-${index}.ohm`);
  fs.writeFileSync(filename, caseSource);
  const coil = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.grammar-dump', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  fs.rmSync(caseDirectory, {recursive: true});
  const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
  if (actual === expected) exact += 1;
  else differences.push({index: `default-${index}`, expected, actual});
}

const comparisonCount = 2 + defaultCases.length;
process.stdout.write(`Compared ${comparisonCount}; exact ${exact}; different ${differences.length}\n`);
for (const difference of differences) {
  process.stdout.write(
    `\ntemplate ${difference.index + 1}\nEXPECTED:\n${difference.expected}\nACTUAL:\n${difference.actual}\n`
  );
}
if (differences.length > 0) process.exitCode = 1;
