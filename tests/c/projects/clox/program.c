#include "chunk.c"
#include "compiler.c"
#include "debug.c"
#include "memory.c"
#include "object.c"
#define advance scanner_advance
#define match scanner_match
#define number scanner_number
#define string scanner_string
#define peek scanner_peek
#include "scanner.c"
#undef advance
#undef match
#undef number
#undef string
#undef peek
#include "table.c"
#include "value.c"
#define call vm_call
#define peek vm_peek
#include "vm.c"
#undef call
#undef peek
#include "main.c"
