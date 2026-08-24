struct point { int x; int y; };
struct line { struct point a; struct point b; int tag; };
union box { char small; long big; };

int grid[2][3] = {{1, 2, 3}, {4, 5, 6}};
int flat[2][3] = {1, 2, 3, 4, 5, 6};
int partial[5] = {7, 8};
int deduced[] = {1, 2, 3, 4};
struct line seg = {{1, 2}, {3, 4}, 9};
struct point sparse = {.y = 11};
char word[8] = "hi";
const char *msg = "abcd";
union box b = {5};

static int counter(void) {
    static int n = 100;
    n++;
    return n;
}

int main(void) {
    int local[4] = {1, 2};
    struct point p = {6, 7};
    struct point q = p;
    char buf[4] = "ab";

    int total = 0;
    for (int i = 0; i < 2; i++)
        for (int j = 0; j < 3; j++)
            total += grid[i][j] + flat[i][j];
    for (int i = 0; i < 5; i++) total += partial[i];
    for (int i = 0; i < 4; i++) total += deduced[i] + local[i];
    total += seg.a.x + seg.a.y + seg.b.x + seg.b.y + seg.tag;
    total += sparse.x + sparse.y;
    total += word[0] + word[1] + word[2] + word[7];
    total += msg[0] + msg[3];
    total += (int) b.big;
    total += p.x + p.y + q.x + q.y;
    total += buf[0] + buf[1] + buf[2];
    total += (int) sizeof(deduced);
    total += counter() + counter();
    return total & 0x7f;
}
