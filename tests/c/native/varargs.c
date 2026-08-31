#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static int sum_ints(int count, ...) {
    va_list ap;
    int total = 0;
    va_start(ap, count);
    for (int i = 0; i < count; i++)
        total += va_arg(ap, int);
    va_end(ap);
    return total;
}

static double sum_doubles(int count, ...) {
    va_list ap;
    double total = 0;
    va_start(ap, count);
    for (int i = 0; i < count; i++)
        total += va_arg(ap, double);
    va_end(ap);
    return total;
}

static int join(char *out, int size, const char *fmt, ...) {
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(out, size, fmt, ap);
    va_end(ap);
    return n;
}

static const char *pick(int which, ...) {
    va_list ap;
    const char *s = "";
    va_start(ap, which);
    for (int i = 0; i <= which; i++)
        s = va_arg(ap, const char *);
    va_end(ap);
    return s;
}

static int sum_list(int count, va_list ap) {
    int total = 0;
    for (int i = 0; i < count; i++) total += va_arg(ap, int);
    return total;
}

static int forward_sum(int count, ...) {
    va_list ap;
    va_start(ap, count);
    int total = sum_list(count, ap);
    va_end(ap);
    return total;
}

int main(void) {
    int total = 0;
    total += sum_ints(4, 1, 2, 3, 4);
    total += (int) sum_doubles(3, 0.5, 1.5, 2.0);

    char buf[64];
    int n = join(buf, sizeof buf, "%s-%d-%c-%.2f", "ab", 17, 'z', 1.25);
    total += n;
    total += strlen(buf);
    total += buf[0] + buf[3];

    total += pick(2, "one", "two", "three")[0];
    total += forward_sum(3, 7, 8, 9);

    printf("%s\n", buf);
    return total & 0x7f;
}
