// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-extract-examples-differential.mjs PINNED_OHM_REPOSITORY');
const {extractExamples} = await import(
  path.join(upstream, 'packages/ohm-js/extras/extractExamples.js')
);

const cases = [
  ['empty', ''],
  ['none', 'G { }'],
  ['simple', '\nG {\n //+ "x"\n start = "x"\n}'],
  ['two-rules', 'G {\n //+ ""\n start = ""\n //+ "x"\n other = ""\n}'],
  ['default', 'G {\n //+ ""\n start = ""\n //+ "hey"\n}'],
  ['outside', '//+ ""\nG {\n start = ""\n //+ "hey"\n}'],
  ['whitespace-1', 'G{  //+ ""\n  }'],
  ['whitespace-2', 'G{  //+ "" \n}'],
  ['whitespace-3', 'G{\n\n//+ ""\n\n}'],
  ['negative', 'G { //+ "blah"\n //- "wooo"\n // - "x"\n start = ""\n}'],
  ['blank', 'G { //+ "blah"\n\n\n start = ""\n}'],
  ['leading', 'G { //+ "blah"\n //+    "wooo"\n start = ""\n}'],
  ['contradictory', 'G { //+ ""\n //- ""\n start = ""\n}'],
  ['duplicate', 'G { //+ ""\n //+ ""\n start = ""\n}'],
  ['json-and-many', 'G {\n //+ "a\\n", "\\uD83D\\uDE00", "\\u0078"\n start = any*\n}'],
  ['multiple-grammars', 'A {\n //+ "a"\n start = "a"\n}\nB {\n //- "b"\n other = "a"\n}'],
];

const output = [];
const field = value => `${Buffer.byteLength(value, 'utf8')}:${value}`;
for (const [label, source] of cases) {
  const found = extractExamples(source);
  output.push(`${label}|${found.length}`);
  for (const item of found) {
    output.push(
      `${field(item.grammar)}|${field(item.rule)}|${field(item.example)}|${item.shouldMatch ? 1 : 0}`
    );
  }
}
const expected = `${output.join('\n')}\n`;
const coil = spawnSync(
  'coil',
  ['run', 'tests/ohm/extract-examples-dump-runtime.coil', '--backend', 'arm64'],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared ${cases.length}; exact ${exact ? cases.length : 0}; different ${exact ? 0 : cases.length}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${JSON.stringify(expected)}\nACTUAL:\n${JSON.stringify(actual)}\n`);
  process.exitCode = 1;
}
