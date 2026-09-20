#define BASE 40
#define INNER(x) ((x) + BASE)
#define STRINGIFY(x) #x
#define JOIN_RAW(x,y) x##y
#define JOIN(x,y) JOIN_RAW(x,y)
int inner_value = INNER(1);
