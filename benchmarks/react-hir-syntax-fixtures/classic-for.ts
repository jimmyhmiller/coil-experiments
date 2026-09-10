for (let index = 0; index < 10; index += 1) {
  if (index == 3) {
    continue;
  }
  if (index == 8) {
    break;
  }
}

for (;;) {
  break;
}

let outside = 0;
for (outside = 1; outside < 3; outside += 1) {
  outside;
}
