#include <stdio.h>

struct point { int x; short y; char z; };
struct entry { const char *name; int n; void (*fn)(void); double d; };
struct bits { unsigned a : 3; unsigned b : 5; int c : 9; };

int ints[5] = {1, -2, 3 * 7, 1 << 20, 'A'};
short shorts[3] = {-1, 32767, -32768};
unsigned char bytes[4] = {0, 255, 128, 1};
long longs[2] = {-9223372036854775807L - 1, 9223372036854775807L};
unsigned long ulongs[2] = {0, 4294967296UL};
double ds[4] = {0.0, -2.5, 0.1, 1e300};
float fs[3] = {0.1f, -1.5f, 3.4e38f};
int grid[2][3] = {{1, 2, 3}, {4, 5, 6}};
struct point pts[2] = {{1, 2, 3}, {-1, -2, -3}};
struct bits bf = {5, 17, -100};
char msg[8] = "hello";
int sparse[6] = {[4] = 9, [1] = 4};
struct point one = {.z = 7, .x = 11};

static void say(void) { printf("said\n"); }
const char *names[2] = {"alpha", "beta"};
struct entry table[2] = {{"first", 1, say, 2.5}, {"second", 2, 0, -0.75}};
int *pnull = 0;
int *pabs = (int *)0x1000;
char c1 = -1;
_Bool flag = 3;
enum { RED = 4, GREEN } colour = GREEN;

int main(void) {
    for (int i = 0; i < 5; i++) printf("%d ", ints[i]);
    printf("\n");
    for (int i = 0; i < 3; i++) printf("%d ", shorts[i]);
    printf("\n");
    for (int i = 0; i < 4; i++) printf("%u ", bytes[i]);
    printf("\n");
    printf("%ld %ld %lu %lu\n", longs[0], longs[1], ulongs[0], ulongs[1]);
    for (int i = 0; i < 4; i++) printf("%.17g ", ds[i]);
    printf("\n");
    for (int i = 0; i < 3; i++) printf("%.9g ", (double)fs[i]);
    printf("\n");
    printf("%d %d %d %d\n", grid[0][0], grid[0][2], grid[1][0], grid[1][2]);
    printf("%d %d %d / %d %d %d\n", pts[0].x, pts[0].y, pts[0].z, pts[1].x, pts[1].y, pts[1].z);
    printf("%u %u %d\n", bf.a, bf.b, bf.c);
    printf("[%s] %d\n", msg, msg[6]);
    for (int i = 0; i < 6; i++) printf("%d ", sparse[i]);
    printf("\n");
    printf("%d %d %d\n", one.x, one.y, one.z);
    printf("%s %s\n", names[0], names[1]);
    printf("%s %d %.2f / %s %d %.2f\n", table[0].name, table[0].n, table[0].d,
           table[1].name, table[1].n, table[1].d);
    table[0].fn();
    printf("%d %d\n", table[1].fn == 0, pnull == 0);
    printf("%p\n", (void *)pabs);
    printf("%d %d %d\n", c1, flag, colour);
    /* A conversion to _Bool is a test against zero, at run time too. */
    int wide = 256;
    _Bool narrow = wide;
    printf("%d %d %d\n", narrow, (_Bool)0.5, (_Bool)(void *)&colour);
    return 0;
}
