double scale = 2.5;
float tiny = 0.125f;
double sci = 1.5e2;
double hexf = 0x1.8p1;

static int truth(double d) { return d ? 1 : 0; }

int main(void) {
    double a = 3.5, b = 2.0;
    int r = 0;
    r += (int) (a + b);
    r += (int) (a - b);
    r += (int) (a * b);
    r += (int) (a / b);
    r += (int) -a;
    r += (a < b) + (a > b) + (a <= b) + (a >= b) + (a == b) + (a != b);
    r += truth(0.0) + truth(0.5) + truth(-0.25);
    r += (int) (scale * 4);
    r += (int) (tiny * 16);
    r += (int) sci;
    r += (int) hexf;

    /* Mixed arithmetic promotes the integer. */
    int n = 3;
    r += (int) (a * n);
    r += (int) (n / 2.0);

    /* Round trips through the narrower type. */
    float f = (float) a;
    r += (int) (f * 2);

    unsigned int big = 4000000000u;
    r += (int) (big / 1000000u);

    long wide = 5000000000L;
    r += (int) (wide / 1000000000L);

    return r & 0x7f;
}
