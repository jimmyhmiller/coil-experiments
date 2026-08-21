/* This portable configuration avoids LZ4's architecture-specific fast decoder.
 * Both comparison binaries use the same configuration. */
#define LZ4_FAST_DEC_LOOP 0
#include "lz4.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
  const int n = 8 * 1024 * 1024;
  char *src = (char *)malloc((size_t)n);
  int bound = LZ4_compressBound(n);
  char *compressed = (char *)malloc((size_t)bound);
  char *decoded = (char *)malloc((size_t)n);
  if (src == NULL || compressed == NULL || decoded == NULL) return 2;

  for (int i = 0; i < n; i++) src[i] = (char)((i * 17 + (i >> 8)) & 255);

  int size = 0;
  int restored = 0;
  for (int iteration = 0; iteration < 20; iteration++) {
    size = LZ4_compress_default(src, compressed, n, bound);
    restored = LZ4_decompress_safe(compressed, decoded, size, n);
  }

  int good = restored == n && memcmp(src, decoded, (size_t)n) == 0;
  printf("%d %d %d\n", n, size, restored);
  free(decoded);
  free(compressed);
  free(src);
  return good ? 0 : 1;
}
