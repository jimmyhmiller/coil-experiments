static int classify(int n) {
    int r = 0;
    switch (n) {
    case 0:
        r += 1;
        break;
    case 1:
    case 2:
        r += 2;
        /* falls through */
    case 3:
        r += 4;
        break;
    default:
        r += 8;
        break;
    case 9:
        r += 16;
    }
    return r;
}

static int no_default(int n) {
    int r = 100;
    switch (n) {
    case 1: r = 1; break;
    case 2: r = 2; break;
    }
    return r;
}

static int assertion_failure_ran = 0;

static void assertion_failure(void) {
    assertion_failure_ran = 1;
}

#define CHECK(expression) \
    (__builtin_expect(!(expression), 0) ? assertion_failure() : (void)0)

int main(void) {
    int total = 0;
    for (int i = 0; i < 11; i++) {
        total += classify(i);
        total += no_default(i);
    }

    /* break and continue must find the right target through a switch. */
    int seen = 0;
    for (int i = 0; i < 10; i++) {
        switch (i % 3) {
        case 0:
            continue;
        case 1:
            break;
        default:
            seen += 100;
            continue;
        }
        seen += 1;
        if (i > 6) break;
    }
    total += seen;

    int j = 0, guard = 0;
    while (j < 20) {
        j++;
        if (j % 2 == 0) continue;
        guard += j;
        if (guard > 40) break;
    }
    total += guard * 1000 + j;

    int k = 0, d = 0;
    do {
        k++;
        if (k == 3) continue;
        d += k;
    } while (k < 6);
    total += d;

    /* A discarded conditional may have void/differently represented arms.
       Darwin's assert macro has this exact shape. */
    CHECK(total != 0);
    total += assertion_failure_ran;

    return total & 0x7f;
}
