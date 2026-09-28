#include <ctype.h>

int check_from_beta(int value)
{
    return isascii(value) && isspace(' ') && value == 41;
}
