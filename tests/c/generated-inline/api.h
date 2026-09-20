#ifndef GENERATED_INLINE_API_H
#define GENERATED_INLINE_API_H
typedef long (*Operation)(long);
#ifndef PROVIDE_EXTERNAL_INLINE
extern inline __attribute__((gnu_inline, always_inline))
long inline_identity(long value) { return value + 1; }
#else
long inline_identity(long value);
#endif
long call(long value);
long owner_value(void);
long native_call_owner(void);
int completed_storage_check(void);
Operation native_inline_address(void);
#endif
