// Repository-development oracle only. Generated parsers never invoke Node.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) {
  throw new Error('usage: node upstream-example-differential.mjs PINNED_OHM_REPOSITORY');
}
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));

function hex(value) {
  return Buffer.from(value, 'utf8').toString('hex');
}

function signature(node) {
  const {startIdx, endIdx} = node.source;
  return `(${hex(node.ctorName)}:${startIdx}:${endIdx}:${hex(node.sourceString)}${node.children
    .map(child => `,${signature(child)}`)
    .join('')})`;
}

function cases(source) {
  const result = [];
  for (const line of source.split(/\r?\n/)) {
    let payload;
    let startRule;
    let escaped = false;
    if (line.startsWith('// @accept-escaped-from ')) {
      payload = line.slice(24);
      const split = payload.indexOf(' ');
      startRule = payload.slice(0, split);
      payload = payload.slice(split + 1);
      escaped = true;
    } else if (line.startsWith('// @accept-escaped ')) {
      payload = line.slice(19);
      escaped = true;
    } else if (line.startsWith('// @accept-from ')) {
      payload = line.slice(16);
      const split = payload.indexOf(' ');
      startRule = payload.slice(0, split);
      payload = payload.slice(split + 1);
    } else if (line.startsWith('// @accept-node ')) {
      payload = line.slice(16);
      const split = payload.indexOf(' ');
      payload = payload.slice(split + 1);
    } else if (line.startsWith('// @accept ')) {
      payload = line.slice(11);
    } else {
      continue;
    }
    if (escaped) {
      payload = payload.replace(/\\([nrt\\])/g, (_, c) =>
        ({n: '\n', r: '\r', t: '\t', '\\': '\\'})[c]
      );
    }
    result.push({input: payload, startRule});
  }
  return result;
}

let compared = 0;
const differences = [];
for (const name of ['upstream-example-math.ohm', 'upstream-example-csv.ohm']) {
  const filename = path.resolve('tests/ohm/conformance', name);
  const source = fs.readFileSync(filename, 'utf8');
  const grammar = ohm.grammar(source);
  const semantics = grammar.createSemantics();
  const expected = cases(source).map(testCase => {
    const match = grammar.match(testCase.input, testCase.startRule);
    if (match.failed()) throw new Error(`${name}: upstream rejected ${JSON.stringify(testCase)}`);
    return signature(semantics(match));
  });
  const coil = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.cst', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  if (coil.status !== 0) {
    throw new Error(`${name}: Coil failed (${coil.status})\n${coil.stderr || coil.stdout}`);
  }
  const actual = coil.stdout.trim().split('\n').filter(Boolean);
  const count = Math.max(expected.length, actual.length);
  for (let index = 0; index < count; index++) {
    compared += 1;
    if (expected[index] !== actual[index]) {
      differences.push({name, index, expected: expected[index], actual: actual[index]});
    }
  }
}

process.stdout.write(`Compared ${compared}; exact ${compared - differences.length}; different ${differences.length}\n`);
for (const difference of differences) {
  process.stdout.write(`\n${difference.name} case ${difference.index}\nEXPECTED:\n${difference.expected}\nACTUAL:\n${difference.actual}\n`);
}
if (differences.length > 0) process.exitCode = 1;
