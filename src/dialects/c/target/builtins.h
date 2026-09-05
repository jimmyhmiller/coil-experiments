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

/* Darwin's FD_ZERO reaches Clang's zero-fill builtin without including
 * <string.h>. Give that intrinsic its specified memory effect directly. */
static void __coil_builtin_bzero(void *__p, unsigned long __n) {
    unsigned char *__bytes = (unsigned char *) __p;
    while (__n != 0) { *__bytes++ = 0; --__n; }
}
#define __builtin_bzero(pointer, size) __coil_builtin_bzero((pointer), (size))

#endif /* __COIL_C_BUILTINS_H */
