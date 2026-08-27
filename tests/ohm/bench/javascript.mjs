import fs from 'node:fs';
import {performance} from 'node:perf_hooks';
import * as ohm from 'ohm-js';
import {Compiler} from '@ohm-js/wasm';
import {WasmGrammar} from '@ohm-js/miniohm-js';

const source = fs.readFileSync(new URL('./grammars.ohm', import.meta.url), 'utf8');
const jsGrammar = ohm.grammar(source);
const wasmGrammar = new WasmGrammar(new Compiler(jsGrammar).compile());

const cases = [
  ['arithmetic-small', 'Arithmetic', '12+34+56+78+90', 20000],
  ['arithmetic-large', 'Arithmetic', '1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20+21+22+23+24+25+26+27+28+29+30+31+32+33+34+35+36+37+38+39+40', 3000],
  ['csv', 'Csv', 'alpha,beta,gamma,delta\none,two,three,four\nfive,six,seven,eight\nnine,ten,eleven,twelve\nred,green,blue,orange\n', 5000],
  ['json', 'Json', '{"name":"coil","items":[1,2,3,4,5,6,7,8],"active":true,"nested":{"x":12.5,"y":null},"tags":["parser","ohm","benchmark"]}', 5000],
];

function benchJs(rule, input, iterations) {
  for (let i = 0; i < 100; i++) {
    if (!jsGrammar.match(input, rule).succeeded()) throw new Error(`JS validation failed: ${rule}`);
  }
  let checksum = 0;
  const start = performance.now();
  for (let i = 0; i < iterations; i++) checksum += jsGrammar.match(input, rule).succeeded();
  return [(performance.now() - start) * 1e6, checksum];
}

function benchWasm(rule, input, iterations) {
  for (let i = 0; i < 100; i++) {
    const result = wasmGrammar.match(input, rule);
    if (!result.succeeded()) throw new Error(`WASM validation failed: ${rule}`);
    result[Symbol.dispose]();
  }
  let checksum = 0;
  const start = performance.now();
  for (let i = 0; i < iterations; i++) {
    const result = wasmGrammar.match(input, rule);
    checksum += result.succeeded();
    result[Symbol.dispose]();
  }
  return [(performance.now() - start) * 1e6, checksum];
}

console.log('engine,case,iterations,elapsed_ns,checksum');
for (const [name, rule, input, iterations] of cases) {
  for (const [engine, fn] of [['javascript', benchJs], ['wasm', benchWasm]]) {
    const [elapsed, checksum] = fn(rule, input, iterations);
    console.log(`${engine},${name},${iterations},${Math.round(elapsed)},${checksum}`);
  }
}
