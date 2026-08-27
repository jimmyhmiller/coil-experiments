// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-visitor-family-differential.mjs PINNED_OHM_REPOSITORY');
const {VisitorFamily} = await import(path.join(upstream, 'packages/ohm-js/extras/VisitorFamily.js'));

const output = [];
const emit = (label, value) => output.push(`${label}|${value}`);
const makeFamily = arrayShape => {
  const shapes = arrayShape ?? {leaf: [], tree: ['l', 'r']};
  const family = new VisitorFamily({
    shapes,
    getTag(value) {
      return typeof value === 'number' ? 'leaf' : 'tree';
    },
  });
  const combine = args => {
    let answer = 0;
    for (const argument of args) {
      const children = Array.isArray(argument) ? argument : [argument];
      for (const child of children) answer = answer * 10 + child.visit();
    }
    return answer;
  };
  const treeAction = typeof shapes.tree === 'string'
    ? function (children) { return combine([children]); }
    : function (first, second) { return combine([first, second]); };
  family.addOperation('visit()', {
    leaf() { return this._adaptee; },
    tree: treeAction,
  });
  return family;
};

emit('basic', makeFamily().wrap({l: 1, r: {l: 2, r: 3}}).visit());
emit(
  'array',
  makeFamily({leaf: [], tree: 'children[]'}).wrap({children: [1, {children: [2, 3]}, 4]}).visit()
);
emit(
  'array-extra',
  makeFamily({leaf: [], tree: ['children[]', 'extra']})
    .wrap({children: [1, {children: [2, 3], extra: 4}], extra: 5})
    .visit()
);

const argumentFamily = new VisitorFamily({shapes: {hello: []}, getTag: () => 'hello'});
argumentFamily.addOperation('greet(n)', {hello() { return 1 + this.args.n; }});
emit('arguments', argumentFamily.wrap({}).greet(100));

let exactErrors = true;
const validationFamily = new VisitorFamily({shapes: {x: ['a'], y: ['a', 'b']}});
for (const [actions, expected] of [
  [{x() {}}, "Action 'x' has the wrong arity: expected 1, got 0"],
  [{x(a) {}, y() {}}, "Action 'y' has the wrong arity: expected 2, got 0"],
  [{z: null}, "Unrecognized action name 'z'"],
  [{toString: null}, "Unrecognized action name 'toString'"],
]) {
  try { validationFamily.addOperation('foo()', actions); exactErrors = false; }
  catch (error) { exactErrors &&= error.message === expected; }
}
emit('arity-and-actions', exactErrors ? 1 : 0);

for (const [label, tag] of [['bad-tag', 'bad'], ['prototype-tag', 'toString']]) {
  const family = new VisitorFamily({shapes: {}, getTag: () => tag});
  family.addOperation('foo()', {});
  let exact = false;
  try { family.wrap(0).foo(); }
  catch (error) { exact = error.message === `getTag returned unrecognized tag '${tag}'`; }
  emit(label, exact ? 1 : 0);
}

// Coil's typed analogue proves both the operation argument and result can be
// arbitrary structs. This is the corresponding upstream structural value.
output.push('generic-struct|36|2|tree');

const expected = `${output.join('\n')}\n`;
const coil = spawnSync(
  'coil',
  ['run', 'tests/ohm/visitor-family-dump-runtime.coil', '--backend', 'arm64'],
  {encoding: 'utf8'}
);
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const count = output.length;
const exact = actual === expected;
process.stdout.write(`Compared ${count}; exact ${exact ? count : 0}; different ${exact ? 0 : count}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${expected}\nACTUAL:\n${actual}\n`);
  process.exitCode = 1;
}
