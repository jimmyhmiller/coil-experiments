#ifndef COIL_MULTI_UNIT_API_H
#define COIL_MULTI_UNIT_API_H

struct Pair {
    int x;
    int y;
};

struct Choice {
    int tag;
    union {
        long number;
        void *pointer;
    } value;
};

extern int shared;
extern int initialized;
int from_alpha(struct Pair *pair);
int from_beta(int value);
int apply(int (*function)(int), int value);
long sum_choices(struct Choice *choices, int count);
void report(const char *label, ...);

#endif
