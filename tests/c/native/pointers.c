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
    return t;
}
