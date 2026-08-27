// Repository-development oracle only. No generated parser invokes Node.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) {
  throw new Error('usage: node upstream-error-differential.mjs PINNED_OHM_REPOSITORY');
}

const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));
const fixtureDirectory = path.resolve('tests/ohm/errors');
const excluded = new Set([
  // This fixture intentionally uses Coil's experimental-indentation provider.
  // Calling public ohm.grammar() without that namespace fails at construction,
  // before the incremental-matcher behavior exercised by the fixture.
  'indentation-incremental-parsing.ohm',
]);

let compared = 0;
let exact = 0;
const differences = [];

for (const name of fs.readdirSync(fixtureDirectory).filter(name => name.endsWith('.ohm')).sort()) {
  if (excluded.has(name)) continue;
  const filename = path.join(fixtureDirectory, name);
  const source = fs.readFileSync(filename, 'utf8');
  let expected;
  try {
    ohm.grammar(source);
    continue;
  } catch (error) {
    expected = error.message;
  }

  const result = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.lang', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = (result.stderr || result.stdout)
    .trim()
    .replace(/^error: /, '')
    .replace(/\nprogram terminated by signal[^]*$/, '')
    .trim();

  compared += 1;
  if (actual === expected) {
    exact += 1;
  } else {
    differences.push({name, expected, actual});
  }
}

for (const name of ['duplicate.ohm', 'undeclared.ohm']) {
  const filename = path.resolve('tests/ohm/namespace-errors', name);
  const source = fs.readFileSync(filename, 'utf8');
  let expected;
  try {
    ohm.grammars(source);
    continue;
  } catch (error) {
    expected = error.message;
  }
  const result = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.namespace', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = (result.stderr || result.stdout).trim().replace(/^error: /, '').trim();
  compared += 1;
  if (actual === expected) exact += 1;
  else differences.push({name: `namespace-errors/${name}`, expected, actual});
}

for (const {name, input, startRule} of [
  {name: 'nullable-dynamic-list-of.ohm', input: 'whatever'},
  {name: 'nullable-dynamic-start-application.ohm', input: 'x', startRule: 'Star<"">'},
  {name: 'parameterized-default-start.ohm', input: 'x'},
  {name: 'missing-default-start-rule.ohm', input: ''},
  {name: 'dynamic-wrong-parameter-count.ohm', input: 'ab', startRule: 'App<"a","b">'},
]) {
  const filename = path.join(fixtureDirectory, name);
  const grammar = ohm.grammar(fs.readFileSync(filename, 'utf8'));
  let expected;
  try {
    grammar.match(input, startRule);
    continue;
  } catch (error) {
    expected = error.message;
  }
  const result = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.lang', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = (result.stderr || result.stdout)
    .trim()
    .replace(/^error: /, '')
    .replace(/\nprogram terminated by signal[^]*$/, '')
    .trim();
  compared += 1;
  if (actual === expected) exact += 1;
  else differences.push({name: `dynamic/${name}`, expected, actual});
}

// Dynamic parameters may change the binding arity of a rule body. Check the
// public semantic Node rather than Ohm's private `_cst`, because the public
// root interval is widened to the complete match.
{
  const name = 'dynamic-arity-changing-argument.ohm';
  const filename = path.resolve('tests/ohm/conformance', name);
  const grammar = ohm.grammar(fs.readFileSync(filename, 'utf8'));
  const match = grammar.match('ab', 'App<"a""b">');
  const node = grammar.createSemantics()(match);
  const expected = `(${Buffer.from(node.ctorName).toString('hex')}:${node.source.startIdx}:${
    node.source.endIdx
  }:${Buffer.from(node.sourceString).toString('hex')})`;
  const result = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.cst', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = (result.stdout || result.stderr).trim();
  compared += 1;
  if (actual === expected) exact += 1;
  else differences.push({name: `dynamic-cst/${name}`, expected, actual});
}

process.stdout.write(`Compared ${compared}; exact ${exact}; different ${differences.length}\n`);
for (const difference of differences) {
  process.stdout.write(
    `\n${difference.name}\nEXPECTED:\n${difference.expected}\nACTUAL:\n${difference.actual}\n`
  );
}
if (differences.length > 0) process.exitCode = 1;
