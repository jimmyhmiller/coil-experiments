static int add_one(int x) { return x + 1; }

static int call_erased(void *erased, int value) {
    return ((int (*)(int))erased)(value);
}

static float sum_axis(const float *axis) {
    return axis[0] + axis[1] + axis[2];
}

static int add_two(int x) { return x + 2; }

int main(void) {
    int xs[5];
    int *p = xs;
    for (int i = 0; i < 5; i++) {
        xs[i] = i * i;
    }
    int t = 0;
    for (int i = 0; i < 5; i++) {
        t += *(p + i);
    }
    int *q = &xs[4];
    t += (int)(q - p);
    t += call_erased((void *)add_one, 9);

    int (*first[])(int) = { add_one };
    int (*second[])(int) = { add_two };
    t += (t ? first : second)[0](10);

    void *none = 0;
    int *selected = t ? p : none;
    int *before = selected ? selected - 0 : 0;
    t += *before;

    t += (int)sum_axis((float[]){ 1, 2, 3 });
    return t;
}
