struct Inner { long value; };
struct Pair { struct Inner inner; long other; };
struct Pair make_pair(long value);
struct Pair advance_pair(struct Pair value);
typedef struct Pair (*Advance)(struct Pair);
Advance owner_advance_address(void);
