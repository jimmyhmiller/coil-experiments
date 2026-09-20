extern int shared_value;

int native_increment(void)
{
    return ++shared_value;
}

int *native_address(void)
{
    return &shared_value;
}
