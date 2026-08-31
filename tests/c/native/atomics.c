static unsigned char byte_value = 3;
static unsigned short short_value = 10;
static unsigned int int_value = 20;
static unsigned long long long_value = 40;

int main(void) {
    int total = 0;
    total += __sync_fetch_and_add(&byte_value, 2);
    total += __sync_fetch_and_sub(&short_value, 3);
    total += __sync_fetch_and_or(&int_value, 4);
    total += (int)__sync_fetch_and_xor(&long_value, 8);
    total += __sync_val_compare_and_swap(&int_value, 24, 7);
    total += __sync_lock_test_and_set(&byte_value, 1);
    __sync_synchronize();
    total += byte_value + short_value + int_value + (int)long_value;
    return total & 0x7f;
}
