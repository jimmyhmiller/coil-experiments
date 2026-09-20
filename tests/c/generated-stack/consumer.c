extern int dynamic_storage(unsigned long);
extern int variable_length_array(unsigned long);

int overwrite_stack(int a, int b, int c, int d, int e, int f, int g, int h, int i)
{
    volatile unsigned char bytes[1024];
    for (int k = 0; k < 1024; k++)
        bytes[k] = 99;
    return a + b + c + d + e + f + g + h + i + bytes[0] - 99;
}

int main(int argc, char **argv)
{
    if (!argv)
        return 1;
    int result = dynamic_storage(32 + argc);
    return result ? result : variable_length_array(32 + argc);
}
