// Repository-development oracle only. Generated parsers never invoke Node.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) {
  throw new Error('usage: node upstream-pexpr-differential.mjs PINNED_OHM_REPOSITORY');
}
const ohm = await import(path.join(upstream, 'packages/ohm-js/index.mjs'));
const p = ohm.pexprs;

function kind(expr) {
  if (expr === p.any) return 14;
  if (expr === p.end) return 15;
  if (expr instanceof p.Terminal) return 1;
  if (expr instanceof p.Range) return 2;
  if (expr instanceof p.Splice) return 13;
  if (expr instanceof p.Extend) return 18;
  if (expr instanceof p.Alt) return 3;
  if (expr instanceof p.Seq) return 4;
  if (expr instanceof p.Star) return 5;
  if (expr instanceof p.Plus) return 6;
  if (expr instanceof p.Opt) return 7;
  if (expr instanceof p.Not) return 8;
  if (expr instanceof p.Lookahead) return 9;
  if (expr instanceof p.Lex) return 10;
  if (expr instanceof p.Param) return 11;
  if (expr instanceof p.Apply) return 12;
  if (expr instanceof p.UnicodeChar) return 16;
  if (expr instanceof p.CaseInsensitiveTerminal) return 17;
  throw new Error(`unknown PExpr ${expr.constructor.name}`);
}

function texts(expr, exprKind) {
  if (exprKind === 1) return [expr.obj, ''];
  if (exprKind === 2) return [expr.from, expr.to];
  if (exprKind === 11) return [`param${expr.index}`, ''];
  if (exprKind === 12) return [expr.ruleName, ''];
  if (exprKind === 16) return [expr.categoryOrProp, ''];
  return ['', ''];
}

function children(expr, exprKind) {
  if (exprKind === 3 || exprKind === 13 || exprKind === 18) return expr.terms;
  if (exprKind === 4) return expr.factors;
  if ([5, 6, 7, 8, 9, 10].includes(exprKind)) return [expr.expr];
  if (exprKind === 12) return expr.args;
  if (exprKind === 17) return [expr.obj];
  return [];
}

function node(expr, grammar) {
  const exprKind = kind(expr);
  const [text, text2] = texts(expr, exprKind);
  const sourceStart = expr.source?.startIdx ?? -1;
  const sourceEnd = expr.source?.endIdx ?? -1;
  let stringValue = '';
  try {
    stringValue = expr.toString();
  } catch {
    // CaseInsensitiveTerminal.toString is intentionally abstract in Ohm 17.
  }
  return [
    exprKind,
    text,
    text2,
    sourceStart,
    sourceEnd,
    stringValue,
    expr.toDisplayString(),
    expr.getArity(),
    expr.isNullable(grammar),
    expr.toArgumentNameList(1),
    children(expr, exprKind).map(child => node(child, grammar)),
  ];
}

function finalGrammar(source) {
  const namespace = ohm.grammars(source);
  const names = Object.keys(namespace);
  return namespace[names[names.length - 1]];
}

function grammarForFixture(name, source) {
  if (name !== 'pexpr-public-definition-source.ohm') return finalGrammar(source);
  const childStart = source.indexOf('G2 <: G');
  const base = ohm.grammar(source.slice(0, childStart));
  return ohm.grammar(source.slice(childStart), {G: base});
}

function signature(grammar) {
  const rules = [];
  const seen = new Set();
  for (let owner = grammar; owner && !owner.isBuiltIn(); owner = owner.superGrammar) {
    for (const name of Object.keys(owner.rules)) {
      if (seen.has(name)) continue;
      seen.add(name);
      const rule = owner.rules[name];
      rules.push([
        name,
        rule.source?.startIdx ?? -1,
        rule.source?.endIdx ?? -1,
        rule.description ?? '',
        rule.formals,
        node(rule.body, grammar),
      ]);
    }
  }
  return JSON.stringify(rules);
}

const fixtures = [
  'pexpr-public-source.ohm',
  'pexpr-public-definition-source.ohm',
  'pexpr-public-display.ohm',
  'pexpr-public-string.ohm',
  'pexpr-public-argument-names.ohm',
];
let exact = 0;
const differences = [];
for (const name of fixtures) {
  const filename = path.resolve('tests/ohm', name);
  const source = fs.readFileSync(filename, 'utf8')
    .split(/(?<=\n)/)
    .filter(line => !line.startsWith('// @pexpr-'))
    .join('');
  const expected = signature(grammarForFixture(name, source));
  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'coil-ohm-pexpr-'));
  const temporaryFixture = path.join(temporaryDirectory, name);
  fs.writeFileSync(temporaryFixture, source);
  const coil = spawnSync(
    'coil',
    ['run', temporaryFixture, '--use', 'experiments.ohm.pexpr-dump', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  fs.rmSync(temporaryDirectory, {recursive: true});
  if (coil.status !== 0) {
    differences.push({name, expected, actual: coil.stderr || coil.stdout});
    continue;
  }
  const actual = coil.stdout.trim();
  if (actual === expected) exact += 1;
  else differences.push({name, expected, actual});
}

{
  const name = 'pexpr-public-definition-source.ohm (ohm.grammars namespace)';
  const filename = path.resolve('tests/ohm/pexpr-public-definition-source.ohm');
  const source = fs.readFileSync(filename, 'utf8');
  const expected = signature(finalGrammar(source));
  const coil = spawnSync(
    'coil',
    ['run', filename, '--use', 'experiments.ohm.namespace-pexpr-dump', '--backend', 'arm64'],
    {encoding: 'utf8'}
  );
  const actual = coil.status === 0 ? coil.stdout.trim() : coil.stderr || coil.stdout;
  if (actual === expected) exact += 1;
  else differences.push({name, expected, actual});
}

const comparisonCount = fixtures.length + 1;
process.stdout.write(`Compared ${comparisonCount}; exact ${exact}; different ${differences.length}\n`);
for (const difference of differences) {
  process.stdout.write(`\n${difference.name}\nEXPECTED:\n${difference.expected}\nACTUAL:\n${difference.actual}\n`);
}
if (differences.length > 0) process.exitCode = 1;
