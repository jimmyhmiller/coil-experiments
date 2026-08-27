// Repository-development oracle only. Generated parsers never invoke Node.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) {
  throw new Error('usage: node upstream-cst-differential.mjs PINNED_OHM_REPOSITORY [FIXTURE]');
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

function decodeEscapes(value) {
  return value.replace(/\\([nrt\\])/g, (_, c) => ({n: '\n', r: '\r', t: '\t', '\\': '\\'})[c]);
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
    } else if (line.startsWith('// @accept-iter ')) {
      payload = line.slice(16);
      const metadata = payload.match(/^\d+ \d+ (?:true|false)(?: |$)/);
      if (!metadata) throw new Error(`invalid @accept-iter directive: ${line}`);
      payload = payload.slice(metadata[0].length);
    } else if (line.startsWith('// @accept ')) {
      payload = line.slice(11);
    } else {
      continue;
    }
    result.push({input: escaped ? decodeEscapes(payload) : payload, startRule});
  }
  return result;
}

function finalGrammar(source) {
  const namespace = ohm.grammars(source, {
    ExperimentalIndentationSensitive: ohm.ExperimentalIndentationSensitive,
    IndentationSensitive: ohm.ExperimentalIndentationSensitive,
  });
  const names = Object.keys(namespace);
  if (names.length === 0) throw new Error('source contains no grammar');
  return namespace[names[names.length - 1]];
}

const requested = process.argv[3];
const directory = path.resolve('tests/ohm/conformance');
const filenames = requested
  ? [path.resolve(requested)]
  : fs.readdirSync(directory)
      .filter(name => name.endsWith('.ohm'))
      .sort()
      .map(name => path.join(directory, name));

let compared = 0;
const differences = [];
const skipped = [];
for (const filename of filenames) {
  const name = path.basename(filename);
  const source = fs.readFileSync(filename, 'utf8');
  const testCases = cases(source);
  if (testCases.length === 0) continue;

  let grammar;
  try {
    grammar = finalGrammar(source);
  } catch (error) {
    skipped.push({name, reason: error.message});
    continue;
  }
  const semantics = grammar.createSemantics();
  const expected = testCases.map(testCase => {
    const match = grammar.match(testCase.input, testCase.startRule);
    if (match.failed()) {
      throw new Error(`${name}: upstream rejected ${JSON.stringify(testCase)}\n${match.message}`);
    }
    return signature(semantics(match));
  });
  const coil = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.cst', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  if (coil.status !== 0) {
    differences.push({name, index: -1, expected: 'successful Coil execution', actual: coil.stderr || coil.stdout});
    continue;
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

process.stdout.write(
  `Compared ${compared}; exact ${compared - differences.length}; different ${differences.length}; skipped ${skipped.length}\n`
);
for (const skip of skipped) process.stdout.write(`SKIP ${skip.name}: ${skip.reason}\n`);
for (const difference of differences) {
  process.stdout.write(
    `\n${difference.name} case ${difference.index}\nEXPECTED:\n${difference.expected}\nACTUAL:\n${difference.actual}\n`
  );
}
if (differences.length > 0 || skipped.length > 0) process.exitCode = 1;
