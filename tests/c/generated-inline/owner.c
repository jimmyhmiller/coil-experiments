#include "api.h"

#if '\x41' != 65 || '\101' != 65
#error numeric character escapes disagree with their values
#endif

extern long completed_storage[];
long completed_storage[1024] = {1};
extern long completed_storage[];
int later_initialized;
enum Forwarding { PLAIN, ALIAS, LOCAL, FORWARDED };
struct ForwardedSymbol { enum Forwarding kind : 2; };
enum SignedState { BELOW = -1, ABOVE = 1 };
struct SignedSymbol { enum SignedState kind : 2; };

int completed_storage_check(void)
{
    const unsigned char *space = (const unsigned char *)"\x00\x7F\0\0\0\0\0\0";
    const unsigned char *escapes = (const unsigned char *)"\377\1017\08\x0000ff" "A";
    struct ForwardedSymbol symbol = { FORWARDED };
    struct SignedSymbol negative = { BELOW };
    completed_storage[1023] = 42;
    return space[0] == 0 && space[1] == 127 && space[7] == 0
        && escapes[0] == 255 && escapes[1] == 65 && escapes[2] == '7'
        && escapes[3] == 0 && escapes[4] == '8' && escapes[5] == 255
        && escapes[6] == 'A' && escapes[7] == 0 && '\x41' == 65 && '\101' == 65
        && symbol.kind == FORWARDED && negative.kind == BELOW && later_initialized == 17
        && sizeof completed_storage == 8192 && completed_storage[0] == 1
        && completed_storage[1023] == 42;
}
long call(long value) { return inline_identity(value); }
long owner_value(void) { return inline_identity(20); }
