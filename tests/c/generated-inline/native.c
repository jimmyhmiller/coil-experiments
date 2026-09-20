#define PROVIDE_EXTERNAL_INLINE
#include "api.h"
long inline_identity(long value) { return value + 1; }
long native_call_owner(void) { return call(owner_value()); }
Operation native_inline_address(void) { return inline_identity; }
