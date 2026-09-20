extern int owner(void);
extern int error(int value, ...);
extern int shared_native;

int main(int argc, char **argv) {
  (void)argc; (void)argv;
  return owner() == 42 && error(20, 1) == 21 && shared_native == 9 ? 0 : 1;
}
