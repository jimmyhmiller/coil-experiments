#include <stdio.h>

typedef unsigned short muint;

typedef struct Note {
    unsigned char sampperiod;
    unsigned char sampeffect;
} note;

typedef struct ModType {
    unsigned char signature[5];
    int channels;
} modtype;

typedef struct Sample {
    unsigned char name[22];
} sample;

static modtype modlist[] = {
    { "M!K!", 4 },
    { "FLT8", 8 },
    { "", 0 }
};

static unsigned later(unsigned value);

static muint decode_sample(note *nptr)
{
    muint sample, period, effect, operiod;
    muint curnote, arpnote;

    sample = (nptr->sampperiod & 0xF0) | (nptr->sampeffect >> 4);
    period = effect = operiod = curnote = arpnote = 0;
    return later(sample + period + effect + operiod + curnote + arpnote + modlist[0].channels - 4);
}

static unsigned later(unsigned value)
{
    return value;
}

int defined_before_extern = 3;
extern int defined_before_extern;

int main(void)
{
    note n = { 0xA0, 0x50 };
    printf("%u\n", (unsigned)decode_sample(&n) + (unsigned)defined_before_extern - 3);
    return 0;
}
