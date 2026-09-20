#include "api.h"
#include <signal.h>
#include <sys/select.h>

int later_initialized = 17;

int main(int argc, char **argv)
{
    sigset_t signals;
    fd_set descriptors;
    sigemptyset(&signals);
    sigaddset(&signals, SIGUSR1);
    FD_ZERO(&descriptors);
    FD_SET(1, &descriptors);
    int present = FD_ISSET(1, &descriptors);
    FD_CLR(1, &descriptors);
    Operation address = native_inline_address();
    return !(argc > 0 && argv && native_call_owner() == 22 && completed_storage_check()
             && inline_identity(41) == 42 && address(41) == 42
             && address == inline_identity && sigismember(&signals, SIGUSR1)
             && present && !FD_ISSET(1, &descriptors));
}
