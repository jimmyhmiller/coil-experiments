#include "doomgeneric.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define VALIDATION_FRAMES 1000

static uint32_t ticks;
static unsigned int frames;

void DG_Init(void)
{
}

void DG_DrawFrame(void)
{
    uint64_t hash = 1469598103934665603ULL;
    unsigned int i;

    if (++frames != VALIDATION_FRAMES)
    {
        return;
    }
    for (i = 0; i < DOOMGENERIC_RESX * DOOMGENERIC_RESY; ++i)
    {
        hash ^= DG_ScreenBuffer[i];
        hash *= 1099511628211ULL;
    }
    printf("doomgeneric: frames=%u frame=%ux%u hash=%016llx\n",
           frames, DOOMGENERIC_RESX, DOOMGENERIC_RESY, (unsigned long long) hash);
    exit(0);
}

void DG_SleepMs(uint32_t milliseconds)
{
    ticks += milliseconds;
}

uint32_t DG_GetTicksMs(void)
{
    return ticks += 29;
}

int DG_GetKey(int *pressed, unsigned char *key)
{
    (void) pressed;
    (void) key;
    return 0;
}

void DG_SetWindowTitle(const char *title)
{
    (void) title;
}

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);
    for (;;)
    {
        doomgeneric_Tick();
    }
}
