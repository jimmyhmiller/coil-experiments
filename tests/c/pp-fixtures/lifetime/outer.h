#include "inner.h"
#define OUTER(x) INNER(x)
#pragma pack(push, 1)
struct packed_value { char tag; int value; };
#pragma pack(pop)
int outer_value = OUTER(0);
