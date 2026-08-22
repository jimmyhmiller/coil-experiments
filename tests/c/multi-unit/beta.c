#include "api.h"
#include <stdio.h>

static int counter = 100;
int shared;
extern int call_increment(int);

static void __attribute__((constructor)) beta_start(void)
{
    shared += 3;
    printf("beta+\n");
}

static void __attribute__((destructor)) beta_stop(void)
{
    printf("beta-\n");
}

static int twice(int value)
{
    return value * 2;
}

int from_beta(int value)
{
    return call_increment(value) + counter;
}

int main(int argc, char **argv)
{
    struct Pair pair = {3, 5};
    struct Choice choices[2];
    choices[0].tag = 1;
    choices[0].value.number = 20;
    choices[1].tag = 1;
    choices[1].value.number = 22;
    int ok = argc > 0 && argv
        && from_alpha(&pair) == 113
        && shared == 8
        && initialized == 7
        && apply(twice, 9) == 18
        && sum_choices(choices, 2) == 42;
    report("linked-varargs", ok);
    printf("main=%d\n", ok);
    return !ok;
}
