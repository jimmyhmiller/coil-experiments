#ifndef COIL_MULTI_UNIT_API_H
#define COIL_MULTI_UNIT_API_H

struct Pair {
    int x;
    int y;
};

extern int shared;
extern int initialized;
int from_alpha(struct Pair *pair);
int from_beta(int value);
int apply(int (*function)(int), int value);

#endif
