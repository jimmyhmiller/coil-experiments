#if '\x41' != 65 || '\101' != 65 || '\0' != 0
#error numeric character escapes disagree with their values
#endif

static const unsigned char initialized[] = "\x00\x7f\377\1017\08\x0000ff" "A";

int main(void)
{
    const unsigned char *literal = (const unsigned char *)"\x00\x7F\377\1017\08\x0000FF" "A";
    unsigned char local[] = "\0\x7f\377";
    const unsigned char expected[] = {0, 127, 255, 65, '7', 0, '8', 255, 'A', 0};
    const unsigned char *simple = (const unsigned char *)"\a\b\f\n\r\t\v\\\"\'\?";
    const unsigned char simple_expected[] = {7, 8, 12, 10, 13, 9, 11, 92, 34, 39, 63, 0};
    if (sizeof initialized != sizeof expected || sizeof local != 4)
        return 1;
    for (unsigned long i = 0; i < sizeof expected; i++)
        if (literal[i] != expected[i] || initialized[i] != expected[i])
            return 2;
    for (unsigned long i = 0; i < sizeof simple_expected; i++)
        if (simple[i] != simple_expected[i])
            return 3;
    if (local[0] != 0 || local[1] != 127 || local[2] != 255 || local[3] != 0)
        return 4;
    return '\x41' != 65 || '\101' != 65;
}
