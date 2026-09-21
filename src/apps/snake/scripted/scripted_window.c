/* Test tooling only: a stand-in for native/snake_window.c with no window.
 *
 * It implements the same ten-function API, but key presses come from a script and
 * the clock is simulated, so a run is deterministic and needs no display. It
 * exists so the key-press probes in ../probes can be checked end to end; the game
 * never links it. */
#include <stdint.h>

#define INPUT_NONE 0
#define INPUT_QUIT 1
#define INPUT_UP 2
#define INPUT_DOWN 3
#define INPUT_LEFT 4
#define INPUT_RIGHT 5

/* A press is delivered once the simulated clock reaches its time. The snake starts
 * heading right, so the LEFT at 900ms is a reversal the engine must ignore. */
static const struct { int64_t at_ms; int64_t code; } script[] = {
    {150, INPUT_DOWN}, {400, INPUT_RIGHT}, {650, INPUT_UP}, {900, INPUT_DOWN},
    {1150, INPUT_LEFT}, {1400, INPUT_DOWN}, {1650, INPUT_DOWN}, {2000, INPUT_QUIT},
};

static int64_t now_ms = 0;
static unsigned long next_press = 0;

int64_t snake_window_open(int64_t cols, int64_t rows, int64_t cell) {
    (void)cols; (void)rows; (void)cell;
    return 0;
}

void snake_window_close(void) {}

int64_t snake_window_poll(void) {
    if (next_press < sizeof script / sizeof script[0] && now_ms >= script[next_press].at_ms)
        return script[next_press++].code;
    return INPUT_NONE;
}

int64_t snake_window_ticks(void) { return now_ms; }

void snake_window_delay(int64_t ms) { now_ms += ms < 0 ? 0 : ms; }

int64_t snake_window_seed(void) { return 7; }

void snake_window_begin_frame(void) {}

void snake_window_draw_cell(int64_t x, int64_t y, int64_t kind) { (void)x; (void)y; (void)kind; }

void snake_window_set_status(int64_t score, int64_t over) { (void)score; (void)over; }

void snake_window_end_frame(void) {}
