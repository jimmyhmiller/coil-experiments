/* Input names remain safe Coil bindings even when native names are forms. */
#include "names.h"
extern int error(int value, ...);
extern int aliased_call(int value) __asm__(NATIVE_ALIAS);
extern int shared_native;

int owner(void) {
  int (*fp)(int) = aliased_call;
  shared_native += 1;
  return error(20, 0) + fp(10) + shared_native;
}
