extern int shared_value;
extern int translated_increment(void);
extern int native_increment(void);
extern int *native_address(void);

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    int *from_native = native_address();
    if (from_native != &shared_value || *from_native != 40)
        return 1;
    if (translated_increment() != 41 || shared_value != 41)
        return 2;
    if (native_increment() != 42 || shared_value != 42)
        return 3;
    return 0;
}
