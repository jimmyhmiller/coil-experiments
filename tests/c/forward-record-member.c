struct Curl_easy;
typedef void callback(struct Curl_easy *data);

struct Curl_easy {
  int set;
};

typedef int Handler(int value);
static Handler add_one, add_two;
static int add_one(int value) { return value + 1; }
static int add_two(int value) { return value + 2; }

static int read_set(const struct Curl_easy *data) {
  return data->set;
}

static int read_conditional_set(const struct Curl_easy *data) {
  return (data ? data : (struct Curl_easy *)0)->set;
}

static int count_bits(unsigned long value) {
  return __builtin_popcountl(value);
}

static int trailing_zeroes(unsigned long value) {
  return __builtin_ctzl(value);
}

static unsigned long swap_bytes(unsigned long value) {
  return __builtin_bswap64(value);
}

int main(void) {
  struct Curl_easy data = {42};
  return read_set(&data) != 42 || read_conditional_set(&data) != 42 ||
         count_bits(0xf0) != 4 || trailing_zeroes(0x10) != 4 ||
         swap_bytes(0x0102030405060708UL) != 0x0807060504030201UL ||
         add_one(1) != 2 || add_two(1) != 3;
}
