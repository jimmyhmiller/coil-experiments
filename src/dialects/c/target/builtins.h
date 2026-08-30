/* The compiler builtins the system headers reach for, written in C.
 *
 * A header like <math.h> is entitled to assume its compiler provides these, and
 * uses them to define isfinite, isnan, signbit and the ordered-comparison
 * macros. Everything here has an ordinary C meaning, so it is given one instead
 * of being special-cased in the compiler: the ones that are genuinely
 * compiler-level -- va_start and its family, offsetof's address arithmetic --
 * stay in the parser, because no C definition of them exists.
 *
 * This header is force-included ahead of the translation unit, so the
 * definitions are in scope before any system header is read.
 */

#ifndef __COIL_C_BUILTINS_H
#define __COIL_C_BUILTINS_H

/* An address computed from the null pointer: the offset of the member from the
 * start of the type. */
#define __builtin_offsetof(type, member) \
        ((unsigned long) &(((type *) 0)->member))

/* The ordered comparisons differ from `<` and `>` only in that they raise no
 * exception on a NaN operand, and this compiler raises none either way. */
#define __builtin_isgreater(x, y)      ((x) > (y))
#define __builtin_isgreaterequal(x, y) ((x) >= (y))
#define __builtin_isless(x, y)         ((x) < (y))
#define __builtin_islessequal(x, y)    ((x) <= (y))
#define __builtin_islessgreater(x, y)  ((x) < (y) || (x) > (y))
#define __builtin_isunordered(x, y)    (!((x) <= (y) || (x) > (y)))

/* Branch-probability metadata does not change the C value of an expression. */
#define __builtin_expect(value, expected) (value)

static float __builtin_fabsf(float __x) { return __x < 0.0f ? -__x : __x; }
static double __builtin_fabs(double __x) { return __x < 0.0 ? -__x : __x; }
static long double __builtin_fabsl(long double __x) { return __x < 0.0 ? -__x : __x; }

/* Dividing by a zero this compiler does not fold is how an infinity is spelled
 * without a constant for one. */
static float __builtin_inff(void) { float __z = 0.0f; return 1.0f / __z; }
static double __builtin_inf(void) { double __z = 0.0; return 1.0 / __z; }
static long double __builtin_infl(void) { double __z = 0.0; return 1.0 / __z; }
static float __builtin_huge_valf(void) { return __builtin_inff(); }
static double __builtin_huge_val(void) { return __builtin_inf(); }
static long double __builtin_huge_vall(void) { return __builtin_infl(); }
static float __builtin_nanf(const char *__t) { float __z = 0.0f; return __z / __z; }
static double __builtin_nan(const char *__t) { double __z = 0.0; return __z / __z; }

/* GCC exposes count-leading-zero operations as builtins. Their result is
 * undefined for zero, so these straightforward definitions only need to match
 * the specified nonzero domain. Keeping them here makes headers that select a
 * GNU implementation compile without adding target-specific AST nodes. */
static int __builtin_clz(unsigned int __x) {
    int __n = 0;
    unsigned int __bit = 1u << 31;
    while ((__x & __bit) == 0) { __n++; __bit >>= 1; }
    return __n;
}

static int __builtin_clzl(unsigned long __x) {
    int __n = 0;
    unsigned long __bit = 1ul << 63;
    while ((__x & __bit) == 0) { __n++; __bit >>= 1; }
    return __n;
}

static int __builtin_clzll(unsigned long long __x) {
    int __n = 0;
    unsigned long long __bit = 1ull << 63;
    while ((__x & __bit) == 0) { __n++; __bit >>= 1; }
    return __n;
}

#endif /* __COIL_C_BUILTINS_H */
