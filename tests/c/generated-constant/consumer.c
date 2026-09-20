extern long remaining_limbs(long);
extern unsigned long long quotient(void);
extern unsigned remainder(void);
extern unsigned narrow_quotient(void);
int main(int argc, char **argv) {
  volatile unsigned long long dividend = ~0ULL;
  volatile unsigned narrow = (unsigned)-1;
  if (remaining_limbs(1) != 2147483645) return 1;
  if (quotient() != dividend / 64 || remainder() != dividend % 64) return 2;
  if (narrow_quotient() != narrow / 64) return 3;
  return 0;
}
