// Repository-development oracle only. The Coil implementation never invokes Node.
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const upstream = process.argv[2];
if (!upstream) throw new Error('usage: node upstream-interval-differential.mjs PINNED_OHM_REPOSITORY');
const {Interval} = await import(path.join(upstream, 'packages/ohm-js/src/Interval.js'));

const lines = [];
const emitInterval = (label, interval) => {
  lines.push(`${label}|${interval.startIdx}|${interval.endIdx}|${interval.sourceString}|${interval.contents}`);
};
const emitOptional = value => (value === null ? 'none' : `some:${value}`);
const emitLine = (label, source, offset) => {
  const info = new Interval(source, offset, offset).getLineAndColumn();
  lines.push(
    `${label}|${info.offset}|${info.lineNum}|${info.colNum}|${info.line}|` +
      `${emitOptional(info.prevLine)}|${emitOptional(info.nextLine)}|`
  );
};

const source = 'hello world';
const interval = new Interval(source, 0, 5);
emitInterval('original', interval);
emitInterval('left', interval.collapsedLeft());
emitInterval('right', interval.collapsedRight());
emitInterval('adjacent', Interval.coverage(new Interval(source, 2, 5), new Interval(source, 0, 2)));
const more = [new Interval(source, 0, 2), new Interval(source, 3, 4), new Interval(source, 6, 10)];
emitInterval('more', Interval.coverage(...more));
emitInterval('coverageWith', more[0].coverageWith(...more));
emitInterval('trimmed', new Interval('xx \t hello \n yy', 2, 13).trimmed());
emitInterval('sub', new Interval('0123456789', 2, 8).subInterval(2, 3));
emitLine('ordinary', 'blah\n3 + 4', 5);
emitLine('empty-next', 'line\n', 0);
emitLine('standalone-cr', 'a\rb', 2);
emitLine('crlf', 'a\r\nb', 3);
emitLine('utf16', '😀\nx', 3);
const expected = `${lines.join('\n')}\n`;

const coil = spawnSync('coil', ['run', 'tests/ohm/interval-dump-runtime.coil', '--backend', 'arm64'], {
  encoding: 'utf8',
});
const actual = coil.status === 0 ? coil.stdout : coil.stderr || coil.stdout;
const exact = actual === expected;
process.stdout.write(`Compared 13; exact ${exact ? 13 : 0}; different ${exact ? 0 : 13}\n`);
if (!exact) {
  process.stdout.write(`EXPECTED:\n${JSON.stringify(expected)}\nACTUAL:\n${JSON.stringify(actual)}\n`);
  process.exitCode = 1;
}
