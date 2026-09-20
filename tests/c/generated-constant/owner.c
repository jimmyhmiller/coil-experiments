/* Reduced from GMP_NLIMBS_MAX and emacs_mpz_mul_2exp in Emacs bignum.c. */
#define UMAX (~0ULL)
enum { limb_limit = (UMAX / 64 < 2147483647 ? UMAX / 64 : 2147483647) };
static unsigned long long initial_quotient = UMAX / 64;
long remaining_limbs(long current) { return limb_limit - 1 - current; }
unsigned long long quotient(void) { return initial_quotient; }
unsigned remainder(void) { enum { value = UMAX % 64 }; return value; }
unsigned narrow_quotient(void) { enum { value = (unsigned)-1 / 64 }; return value; }
