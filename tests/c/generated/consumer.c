#include "api.h"

int main(int argc, char **argv)
{
    struct Pair value = make_pair(41);
    struct Pair (*advance)(struct Pair) = advance_pair;
    value = advance(value);
    Advance from_owner = owner_advance_address();
    struct Pair owner_value = from_owner(make_pair(41));
    return !(argc > 0 && argv && value.inner.value == 42 && value.other == 1
             && from_owner == advance_pair && owner_value.inner.value == 42);
}
