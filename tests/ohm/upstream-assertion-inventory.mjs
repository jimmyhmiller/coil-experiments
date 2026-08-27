// Repository-development oracle only. This never participates in a Coil parser.
import fs from 'node:fs';
import path from 'node:path';

const root = process.argv[2];
if (!root) {
  throw new Error('usage: node upstream-assertion-inventory.mjs OHM_TEST_DIRECTORY');
}

function filesBelow(directory) {
  return fs.readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
    const full = path.join(directory, entry.name);
    return entry.isDirectory() ? filesBelow(full) : [full];
  });
}

function lineAt(source, offset) {
  return 1 + source.slice(0, offset).split('\n').length - 1;
}

function lineTextAt(source, offset) {
  const start = source.lastIndexOf('\n', offset - 1) + 1;
  const end = source.indexOf('\n', offset);
  return source.slice(start, end < 0 ? source.length : end).trim();
}

function stablePart(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

const files = filesBelow(root)
  .filter(file => /\.(?:c?js|mjs)$/.test(file))
  .sort();

const inventory = [];
for (const file of files) {
  const source = fs.readFileSync(file, 'utf8');
  const relativeFile = path.relative(root, file);
  const tests = [...source.matchAll(/\b(?:test|test\.failing|test\.skip)\s*\(\s*(['"`])([^\n]*?)\1/g)]
    .map((match, index, matches) => {
      const start = match.index;
      const end = matches[index + 1]?.index ?? source.length;
      const body = source.slice(start, end);
      const assertions = [...body.matchAll(/\bt\.([A-Za-z][A-Za-z0-9_]*)\s*\(/g)]
        .map((assertion, assertionIndex) => {
          const offset = start + assertion.index;
          return {
            id: `${relativeFile}:${lineAt(source, offset)}:${assertionIndex + 1}`,
            kind: assertion[1],
            line: lineAt(source, offset),
            source: lineTextAt(source, offset),
          };
        });
      const line = lineAt(source, start);
      return {
        id: `${relativeFile}:${line}:${stablePart(match[2])}`,
        name: match[2],
        line,
        assertions,
      };
    });
  inventory.push({file: relativeFile, tests});
}

const summary = {
  files: inventory.length,
  tests: inventory.reduce((sum, file) => sum + file.tests.length, 0),
  assertions: inventory.reduce(
    (sum, file) => sum + file.tests.reduce((n, test) => n + test.assertions.length, 0),
    0
  ),
};

process.stdout.write(`${JSON.stringify({summary, files: inventory}, null, 2)}\n`);
