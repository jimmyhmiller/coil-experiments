function classify(value: number) {
  switch (value) {
    case 0:
      return "zero";
    case 1:
    case 2:
      value = value + 10;
      break;
    default:
      value = 99;
    case 3:
      value = value + 1;
  }
  return value;
}

switch (classify(2)) {}

while (value) {
  switch (value) {
    case 4:
      value = value - 1;
      continue;
    default:
      break;
  }
  break;
}
