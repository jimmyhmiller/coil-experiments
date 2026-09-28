#include <ctype.h>

int main(void)
{
    struct LocalRecord { int first; int second; };
    struct LocalRecord record = { 20, 21 };
    int check_from_beta(int);
    return isascii(65) && check_from_beta(record.first + record.second) ? 0 : 1;
}
