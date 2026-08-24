/* Assignments whose target has side effects of its own, and the integer
 * conversions that surround a pointer index. Both were wrong once: the address
 * of an assignment's target was computed twice, once for the store and once to
 * read the value back, and an index declared `short` was scaled to bytes in 16
 * bits and overflowed. */
#include <stdio.h>

typedef struct { int first; int last; } range_t;

static range_t segs[8];
static short small_index;

struct bits { unsigned a : 3; unsigned b : 5; };

int main(void) {
    for (int i = 0; i < 8; i++) { segs[i].first = i; segs[i].last = 100 + i; }

    range_t *end = segs + 5;
    range_t *next = segs + 1;
    range_t *start = segs;
    while (next++ != end)
        *++start = *next;
    printf("next=%d start=%d\n", (int)(next - segs), (int)(start - segs));
    for (int i = 0; i < 8; i++)
        printf("%d: %d %d\n", i, segs[i].first, segs[i].last);

    int xs[4] = {0, 0, 0, 0};
    int *p = xs;
    *p++ = 1;
    *p++ = 2;
    printf("xs %d %d %d p=%d\n", xs[0], xs[1], xs[2], (int)(p - xs));

    int i = 0;
    xs[i++] = 9;
    printf("i=%d xs0=%d\n", i, xs[0]);

    /* A bitfield store reads and writes one storage unit; its address is
     * likewise computed once. */
    struct bits k[2];
    struct bits *bp = k;
    k[0].a = 0; k[0].b = 0; k[1].a = 0; k[1].b = 0;
    (bp++)->a = 5;
    bp->b = 17;
    printf("bits %d %d %d %d bp=%d\n", k[0].a, k[0].b, k[1].a, k[1].b, (int)(bp - k));

    /* A short index into an array whose elements are big enough that the
     * scaled offset leaves 16-bit range. */
    static int wide[1200];
    for (int j = 0; j < 1200; j++) wide[j] = j;
    small_index = 1100;
    printf("wide=%d\n", wide[small_index]);

    struct big { int pad[14]; } *bigs;
    static struct big table[700];
    bigs = table;
    for (int j = 0; j < 700; j++) table[j].pad[0] = j;
    small_index = 650;
    printf("big=%d\n", bigs[small_index].pad[0]);
    return 0;
}
