long sparse[708334] = { [708333] = 42, [0] = 1, [13] = 9, [13] = 17 };
long nested[2][708334] = { [1] = { [708333] = 73 } };
long inferred[] = { [999] = 7, [0] = 4 };
char greeting[708334] = "hi";
long *native_image(void) { return sparse; }
long *native_nested(void) { return &nested[0][0]; }
long check_owner(void) {
  long local[1000] = { [999] = 7, [0] = 4 };
  long range[] = { [2 ... 4] = 9, [0] = 3 };
  return sizeof inferred == 8000 && inferred[998] == 0 && inferred[999] == 7
    && local[0] == 4 && local[998] == 0 && local[999] == 7
    && sizeof range == 40 && range[0] == 3 && range[1] == 0 && range[4] == 9
    && greeting[0] == 'h' && greeting[1] == 'i' && greeting[2] == 0 && greeting[708333] == 0;
}
