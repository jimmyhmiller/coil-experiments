int main(void) {
    int a = 7, b = 3;
    int r = 0;
    r += a + b; r += a - b; r += a * b; r += a / b; r += a % b;
    r += (a << 2) + (a >> 1);
    r += (a & b) + (a | b) + (a ^ b);
    r += (a < b) + (a > b) + (a <= b) + (a >= b) + (a == b) + (a != b);
    r += (a && b) + (a || 0) + !a;
    return r & 0x7f;
}
