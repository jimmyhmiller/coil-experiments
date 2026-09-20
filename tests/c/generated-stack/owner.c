extern int overwrite_stack(int, int, int, int, int, int, int, int, int);

int dynamic_storage(unsigned long count)
{
    unsigned char *first = __builtin_alloca(count);
    unsigned char *second = __builtin_alloca(count);
    unsigned char *iterations[4];
    if (first == second)
        return 1;
    if (((unsigned long)first & 15) || ((unsigned long)second & 15))
        return 2;
    first[0] = 21;
    second[count - 1] = 22;
    for (int i = 0; i < 4; i++) {
        iterations[i] = __builtin_alloca(count + i);
        iterations[i][count + i - 1] = 30 + i;
    }
    if (overwrite_stack(1, 2, 3, 4, 5, 6, 7, 8, 9) != 45)
        return 3;
    if (first[0] != 21 || second[count - 1] != 22)
        return 4;
    for (int i = 0; i < 4; i++)
        if (iterations[i][count + i - 1] != 30 + i)
            return 5;
    return 0;
}

int variable_length_array(unsigned long count)
{
    /* A block-scope static const is deliberately not an integer constant
       expression in C, so this exercises the VLA lowering used by pdumper.c. */
    static const int candidates = 3;
    unsigned long values[candidates + count];
    for (unsigned long i = 0; i < candidates + count; i++)
        values[i] = 1000 + i;
    if (overwrite_stack(1, 2, 3, 4, 5, 6, 7, 8, 9) != 45)
        return 6;
    for (unsigned long i = 0; i < candidates + count; i++)
        if (values[i] != 1000 + i)
            return 7;
    return 0;
}
