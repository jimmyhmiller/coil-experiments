enum Kind { FIRST = 3, SECOND };
typedef int (*operation)(int, int);
int add(int a, int b) { return a + b; }
int apply(operation f, int *v) { return f(v[0], v[1]); }
int main(void) { int v[2] = { FIRST, SECOND }; return apply(add, v) == 7 ? 0 : 1; }
