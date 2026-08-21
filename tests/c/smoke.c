#include <stdio.h>

typedef struct Pair { int x, y; } Pair;

static int dot(Pair *p, int scale) {
  int sum = 0;
  for (int i = 0; i < 4; ++i) sum += (p->x + p->y) * scale;
  return sum;
}

int main(void) {
  Pair p = { 2, 3 };
  printf("%d\n", dot(&p, 2));
  return 0;
}
