struct point {
    int x;
    int y;
};

union value {
    char small;
    long big;
};

struct packed {
    unsigned a : 3;
    unsigned b : 5;
    unsigned c : 1;
};

int main(void) {
    struct point p;
    p.x = 3;
    p.y = 4;

    struct point *q = &p;
    q->x = q->x + q->y;

    union value v;
    v.big = 0;
    v.small = 9;

    struct packed k;
    k.a = 5;
    k.b = 17;
    k.c = 1;

    int sizes = (int) (sizeof(struct point) + sizeof(union value) + sizeof(struct packed));
    return (p.x + (int) v.small + (int) k.a + (int) k.b + (int) k.c + sizes) & 0x7f;
}
