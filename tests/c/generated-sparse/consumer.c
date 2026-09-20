extern long sparse[708334], nested[2][708334];
long check_owner(void), check_native(void);
int main(int argc, char **argv) {
  if (!check_owner() || !check_native()) return 1;
  if (sparse[13] != 17 || sparse[708333] != 42 || nested[1][708333] != 73) return 2;
  sparse[350000] = 99;
  return sparse[350000] == 99 ? 0 : 3;
}
