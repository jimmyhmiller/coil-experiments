#include "api.h"

struct Pair make_pair(long value)
{
    struct Pair result = {{value}, 1};
    return result;
}

struct Pair advance_pair(struct Pair value)
{
    value.inner.value += value.other;
    return value;
}

Advance owner_advance_address(void)
{
    return advance_pair;
}
