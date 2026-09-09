#include <stddef.h>

// Built as a separate object so Coil's whole-program optimizer must treat the
// pointed-to bytes as observable, without adding a traversal to the benchmark.
__attribute__((noinline)) void coil_benchmark_consume(const void *data,
                                                       size_t bytes) {
  __asm__ volatile("" : : "r"(data), "r"(bytes) : "memory");
}
