const mapped = values.map(function (value, index) {
  return value + index;
});

const factorial = function recur(value: number): number {
  if (value <= 1) return 1;
  return value * recur(value - 1);
};

const identity = function<T>(value: T): T {
  return value;
};
