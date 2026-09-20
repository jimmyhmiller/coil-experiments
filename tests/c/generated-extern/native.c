#include "names.h"
int shared_native = 8;
int error(int value, ...) { return value + 1; }
int native_alias(int value) __asm__(NATIVE_ALIAS);
int native_alias(int value) { return value + 2; }
