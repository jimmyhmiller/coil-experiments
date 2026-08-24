#include <stdio.h>

/* A forward jump out of nested loops, the shape a search uses. */
static int find(int limit) {
    int i = 0, j = 0, hits = 0;
    for (i = 0; i < limit; i++) {
        for (j = 0; j < limit; j++) {
            if (i * j > 6)
                goto done;
            hits++;
        }
    }
done:
    return hits * 100 + i * 10 + j;
}

/* A backward jump, which is a loop written by hand. */
static int retry(int n) {
    int tries = 0;
again:
    tries++;
    n = n / 2;
    if (n > 0)
        goto again;
    return tries;
}

/* A jump out of a switch, and a jump into the middle of what follows it. */
static int classify(int n) {
    int score = 0;
    switch (n) {
    case 0:
        score += 1;
        goto tail;
    case 1:
    case 2:
        score += 2;
        break;
    default:
        score += 4;
        goto middle;
    }
    score += 8;
middle:
    score += 16;
tail:
    return score;
}

/* Labels interleaved with declarations and loops. */
static int weave(int n) {
    int total = 0;
    int k = 0;
top:
    if (k >= n)
        goto out;
    {
        int step = k * 2;
        if (step % 3 == 0) {
            k++;
            goto top;
        }
        total += step;
    }
    k++;
    goto top;
out:
    while (total > 50) {
        total -= 7;
        if (total == 43)
            goto out2;
    }
out2:
    return total;
}

int main(void) {
    int total = 0;
    for (int i = 0; i < 6; i++) total += find(i);
    for (int i = 1; i < 40; i++) total += retry(i);
    for (int i = 0; i < 5; i++) total += classify(i);
    for (int i = 0; i < 20; i++) total += weave(i);
    printf("%d\n", total);
    return total & 0x7f;
}
