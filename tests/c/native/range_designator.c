#include <stdio.h>

static int values[7] = {[1 ... 4] = 9, [6] = 2};

int main(void) {
    int sum = 0;
    for (int i = 0; i < 7; ++i) sum += values[i];
    printf("%d %d %d\n", values[0], values[3], values[5]);
    return sum == 38 ? 0 : 1;
}
