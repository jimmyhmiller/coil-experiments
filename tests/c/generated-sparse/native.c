long *native_image(void), *native_nested(void);
static int valid;
__attribute__((constructor)) static void before_main(void) {
  long *a = native_image(), *n = native_nested();
  valid = 1;
  for (int i = 0; i < 708334; ++i) {
    long want = i == 0 ? 1 : i == 13 ? 17 : i == 708333 ? 42 : 0;
    if (a[i] != want || n[i] || n[708334+i] != (i == 708333 ? 73 : 0)) valid = 0;
  }
}
long check_native(void) { return valid; }
