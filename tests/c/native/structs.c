/* Records crossing function boundaries by value, nested and copied. */
#include <stdio.h>

typedef struct { int x, y; } point_t;
typedef struct { point_t a, b; char tag; } span_t;
typedef struct { double w; float h; } size_t_;

static point_t move(point_t p, int dx, int dy) {
    p.x += dx;
    p.y += dy;
    return p;
}

static int span_area(span_t s) {
    return (s.b.x - s.a.x) * (s.b.y - s.a.y) + s.tag;
}

static span_t grow(span_t s, int by) {
    s.a = move(s.a, -by, -by);
    s.b = move(s.b, by, by);
    return s;
}

static size_t_ halve(size_t_ s) {
    s.w /= 2;
    s.h /= 2;
    return s;
}

/* Opaque to everything but this file: a pointer to an incomplete record has to
 * pass through a function declared with the incomplete spelling. */
typedef struct hidden hidden_t;
static int hidden_value(hidden_t *h);

struct hidden { int a; int b; };
static struct hidden the_hidden = { 3, 4 };

static int hidden_value(hidden_t *h) { return h->a * 10 + h->b; }

int main(void) {
    point_t p = { 2, 3 };
    point_t q = move(p, 5, 7);
    printf("p=%d,%d q=%d,%d\n", p.x, p.y, q.x, q.y);

    span_t s = { { 0, 0 }, { 4, 5 }, 9 };
    printf("area=%d\n", span_area(s));

    span_t g = grow(s, 2);
    printf("g=%d,%d..%d,%d tag=%d area=%d\n",
           g.a.x, g.a.y, g.b.x, g.b.y, g.tag, span_area(g));
    printf("s unchanged=%d,%d..%d,%d\n", s.a.x, s.a.y, s.b.x, s.b.y);

    size_t_ z = { 9.0, 5.0f };
    size_t_ h = halve(z);
    printf("z=%.2f,%.2f h=%.2f,%.2f\n", z.w, (double) z.h, h.w, (double) h.h);

    span_t copy = s;
    copy.tag = 1;
    printf("copy tag=%d orig tag=%d\n", copy.tag, s.tag);

    printf("hidden=%d\n", hidden_value(&the_hidden));
    return 0;
}
