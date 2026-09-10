let count = 0;
do {
  count += 1;
  if (count == 2) {
    continue;
  }
  if (count == 4) {
    break;
  }
} while (count < 10);

do {
  break;
  count = 100;
} while (false);
