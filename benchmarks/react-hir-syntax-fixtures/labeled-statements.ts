outer: inner: for (let i = 0; i < 10; i++) {
  if (i === 2) continue outer;
  if (i === 8) break inner;
}

blockLabel: {
  if (condition) break blockLabel;
  work();
}

finished: returnValue();

sameName: while (condition) {
  function nested() {
    sameName: while (otherCondition) break sameName;
  }
  break sameName;
}
