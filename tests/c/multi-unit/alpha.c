#include "api.h"
#include <stdarg.h>
#include <stdio.h>

static int counter = 4;
int shared;
int initialized = 7;
int initialized;

static void __attribute__((constructor)) alpha_start(void)
{
    shared = 2;
    if (initialized != 7) shared = -100;
    printf("alpha+\n");
}

static void __attribute__((destructor)) alpha_stop(void)
{
    printf("alpha-\n");
}

static int increment(int value)
{
    return value + counter;
}

void report(const char *label, ...)
{
    va_list arguments;
    va_start(arguments, label);
    printf("%s=%d\n", label, va_arg(arguments, int));
    va_end(arguments);
}

int from_alpha(struct Pair *pair)
{
    shared += pair->x;
    return from_beta(pair->y) + counter;
}

int apply(int (*function)(int), int value)
{
    return function(value);
}

long sum_choices(struct Choice *choices, int count)
{
    long total = 0;
    int i;
    for (i = 0; i < count; ++i)
    {
        total += choices[i].value.number;
    }
    return total;
}

int call_increment(int value)
{
    return increment(value);
}
