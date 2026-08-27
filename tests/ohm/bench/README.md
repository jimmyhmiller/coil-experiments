# Ohm parser benchmarks

This benchmark compiles one [`grammars.ohm`](grammars.ohm) file through all
three implementations:

- the Coil Ohm reader, imported through `[readers]` and built with `--release`;
- Coil's handwritten `coil.json` tape parser for the native JSON comparison;
- `ohm-js` 17.5.0;
- `@ohm-js/wasm` 0.7.5 with `@ohm-js/miniohm-js` 0.5.0.

Grammar construction and Wasm compilation/instantiation happen outside the
timed loops. Each case gets 100 warmup parses. Every timed parse checks success,
and owned Coil/Wasm match results are freed or disposed on every iteration.
The `json-handwritten` row also reads the produced document's token count before
freeing it, so the compact tape is observable.

The JSON rows intentionally answer a lower-bound question, not an equivalent
output comparison. The benchmark Ohm grammar currently recognizes a JSON subset
and returns a full Ohm CST. `coil.json` validates complete JSON and returns the
compact `json/Doc` tape used by Coil programs. Converting the CST into that tape
would add cost to the generated parser's measured time.

Run from this directory:

```sh
npm install
coil build --release -o /tmp/ohm-native-bench

for run_index in 1 2 3 4 5; do
  /tmp/ohm-native-bench
done

for run_index in 1 2 3 4 5; do
  node javascript.mjs
done
```

Compare medians across the five samples. The emitted CSV contains a checksum;
it must equal `iterations` for every row.

The uppercase `Start` rule keeps every benchmark entry point reachable to the
experimental Wasm compiler. `Csv` uses `#csv` because newline is significant in
CSV, while normal uppercase Ohm rules implicitly skip whitespace (including
newlines).
