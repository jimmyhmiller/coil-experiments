# C reader application corpus

These are pinned upstream sources used to validate whole-program native C
translation. Each directory retains its upstream license.

| Project | Revision | Source lines exercised | Validation |
| --- | --- | ---: | --- |
| clox / Crafting Interpreters | `4a840f70f69c6ddd17cfef4f6964f8e1bcd8c3d4` | 4,979 | 246 language tests and recursive Fibonacci benchmark |
| cJSON | `fb16e5cf358798aabb049655975cde8427101056` | 3,206 | parse/traverse/print/free round trip |
| LZ4 | `0774d05537f9762f838f7ab541b7765f1a729cb5` | 2,848 | 20 compression/decompression rounds over 8 MiB with byte comparison |

`program.c` is the whole-program entry for each project. cJSON also has a
`separate-program.c` entry used to validate real multi-translation-unit linking.
LZ4 uses its documented
portable decoder configuration (`LZ4_FAST_DEC_LOOP=0`) in both the Clang and Coil
builds; this avoids an architecture-specific cross-loop goto fast path while
testing the complete portable codec implementation.
