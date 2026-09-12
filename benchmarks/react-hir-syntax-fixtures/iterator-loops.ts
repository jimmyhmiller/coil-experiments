let key;
for (key in object) {
  if (key === "skip") continue;
  consume(key);
}

for (const value of values) {
  if (!value) break;
  consume(value);
}

for (let [index, item] of entries) {
  consume(index, item);
}

for (const {name} of records) {
  consume(name);
}

for (state.current of records) {
  consume(state.current);
}

for await (const value of asyncValues) {
  consume(value);
}
