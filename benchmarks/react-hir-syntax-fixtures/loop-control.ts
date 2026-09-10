let value = 0;
while (value < 10) {
  if (value == 3) {
    break;
  }
  if (value == 1) {
    value += 1;
    continue;
  }
  value += 2;
}

while (true) {
  while (false) {
    continue;
  }
  break;
}
