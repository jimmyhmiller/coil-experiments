/* Parser-required constants and static initializers must agree with execution. */
#define UMAX (~0ULL)
enum { limb_limit = (UMAX / 64 < 2147483647 ? UMAX / 64 : 2147483647) };
enum { quotient = (unsigned)-1 / 64, remainder = UMAX % 64 };
static unsigned long long initial_quotient = UMAX / 64;
static unsigned long long initial_remainder = UMAX % 64;
static unsigned cast_quotient = (unsigned)-1 / 64;
static int signed_quotient = -65 / 64;
static int signed_remainder = -65 % 64;
int main(void) {
  volatile unsigned long long dividend = UMAX, divisor = 64;
  volatile unsigned narrow = (unsigned)-1;
  if (limb_limit != 2147483647) return 1;
  if (quotient != narrow / divisor || remainder != dividend % divisor) return 2;
  if (initial_quotient != dividend / divisor) return 3;
  if (initial_remainder != dividend % divisor || cast_quotient != quotient) return 4;
  if (signed_quotient != -1 || signed_remainder != -1) return 5;
  if ((unsigned char)511 != 255 || (signed char)255 != -1) return 6;
  return 0;
}
