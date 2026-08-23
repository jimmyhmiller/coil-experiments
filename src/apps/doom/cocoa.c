/* A native macOS platform backend for Doom Generic, in plain C.
 *
 * Doom Generic asks its host for six things: a window, a framebuffer blit, a
 * clock, a sleep, a key queue, and a title. Everything below is ordinary C
 * compiled by the native Coil C frontend -- there is no Objective-C compiler
 * and no wrapper library. Cocoa is reached the way it actually works
 * underneath: every message send is a call to objc_msgSend, which on arm64
 * must be made through a function pointer carrying the selector's exact
 * signature, so the base declaration is retyped at each call site. The same
 * technique as src/apps/chip8/objc.coil, spelled in C.
 *
 *   python3 scripts/doom-play.py --compiler "$(command -v coil)"
 *
 * Move with the arrow keys, fire with ctrl, open with space, strafe with alt,
 * escape for the menu.
 */
#include "doomgeneric.h"
#include "doomkeys.h"
#include "d_event.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* --- Objective-C runtime ------------------------------------------------ */

typedef void *id;
typedef void *SEL;

extern id objc_getClass(const char *name);
extern SEL sel_registerName(const char *name);

/* Base declaration only; never called through this type. */
extern id objc_msgSend(id self, SEL op);

#define SEND0(ret, recv, sel) \
    ((ret (*)(id, SEL))objc_msgSend)((recv), (sel))
#define SEND1(ret, recv, sel, t1, a1) \
    ((ret (*)(id, SEL, t1))objc_msgSend)((recv), (sel), (a1))
#define SEND4(ret, recv, sel, t1, t2, t3, t4, a1, a2, a3, a4) \
    ((ret (*)(id, SEL, t1, t2, t3, t4))objc_msgSend)((recv), (sel), (a1), (a2), (a3), (a4))

#define CLS(name) ((id) objc_getClass(name))
#define SEL_(name) sel_registerName(name)

/* --- CoreGraphics ------------------------------------------------------- */

typedef struct { double x, y, w, h; } CGRect_t;

extern void *CGColorSpaceCreateDeviceRGB(void);
extern void CGColorSpaceRelease(void *space);
extern void *CGBitmapContextCreate(void *data, unsigned long width, unsigned long height,
                                   unsigned long bits_per_component,
                                   unsigned long bytes_per_row,
                                   void *space, unsigned int info);
extern void *CGBitmapContextCreateImage(void *context);
extern void CGContextRelease(void *context);
extern void CGImageRelease(void *image);

/* kCGImageAlphaNoneSkipFirst | kCGBitmapByteOrder32Little: the memory order of
   Doom Generic's pixel_t, which is 0x00RRGGBB in a native uint32. */
#define DG_BITMAP_INFO (6u | (2u << 12))

/* --- Cocoa constants ---------------------------------------------------- */

#define NS_TITLED           1
#define NS_CLOSABLE         2
#define NS_MINIATURIZABLE   4
#define NS_RESIZABLE        8
#define NS_BACKING_BUFFERED 2

#define NS_LEFT_MOUSE_DOWN   1
#define NS_LEFT_MOUSE_UP     2
#define NS_RIGHT_MOUSE_DOWN  3
#define NS_RIGHT_MOUSE_UP    4
#define NS_MOUSE_MOVED       5
#define NS_LEFT_MOUSE_DRAG   6
#define NS_RIGHT_MOUSE_DRAG  7
#define NS_KEY_DOWN         10
#define NS_KEY_UP           11
#define NS_FLAGS_CHANGED    12
#define NS_OTHER_MOUSE_DOWN 25
#define NS_OTHER_MOUSE_UP   26
#define NS_OTHER_MOUSE_DRAG 27

#define NS_FLAG_SHIFT   0x20000
#define NS_FLAG_CONTROL 0x40000
#define NS_FLAG_OPTION  0x80000

/* macOS virtual key codes, which are layout independent. */
#define VK_RETURN 0x24
#define VK_TAB    0x30
#define VK_SPACE  0x31
#define VK_DELETE 0x33
#define VK_ESCAPE 0x35
#define VK_LEFT   0x7B
#define VK_RIGHT  0x7C
#define VK_DOWN   0x7D
#define VK_UP     0x7E

/* --- state -------------------------------------------------------------- */

#define KEYQUEUE_SIZE 32

static unsigned short key_queue[KEYQUEUE_SIZE];
static unsigned int key_write;
static unsigned int key_read;

static id app;
static id window;
static id layer;
static id run_loop_mode;
static unsigned long modifiers;
static uint32_t start_ms;

/* Doom reads the mouse as a per-tic delta plus a button bitfield, so motion is
   accumulated between frames rather than posted per event. */
static int mouse_buttons;
static double mouse_dx;
static double mouse_dy;
static int last_buttons;

extern int CGAssociateMouseAndMouseCursorPosition(int connected);

/* Darwin's nanosecond clock is used rather than gettimeofday because it takes
   and returns scalars: a record declared in a system header is opaque to
   generated Coil, so `struct timeval` could not be a local here. */
static uint32_t now_ms(void)
{
    return (uint32_t) (clock_gettime_nsec_np(CLOCK_UPTIME_RAW) / 1000000u);
}

static void queue_key(int pressed, unsigned char key)
{
    if (key == 0)
    {
        return;
    }
    key_queue[key_write] = (unsigned short) ((pressed << 8) | key);
    key_write = (key_write + 1) % KEYQUEUE_SIZE;
}

static unsigned char translate_key(unsigned short code, const char *characters)
{
    switch (code)
    {
    case VK_LEFT:   return KEY_LEFTARROW;
    case VK_RIGHT:  return KEY_RIGHTARROW;
    case VK_UP:     return KEY_UPARROW;
    case VK_DOWN:   return KEY_DOWNARROW;
    case VK_ESCAPE: return KEY_ESCAPE;
    case VK_RETURN: return KEY_ENTER;
    case VK_TAB:    return KEY_TAB;
    case VK_SPACE:  return KEY_USE;
    case VK_DELETE: return KEY_BACKSPACE;
    default:        break;
    }

    if (characters != 0 && characters[0] != '\0')
    {
        unsigned char c = (unsigned char) characters[0];

        if (c >= 'A' && c <= 'Z')
        {
            c = (unsigned char) (c - 'A' + 'a');
        }
        if (c >= ' ' && c < 0x7f)
        {
            return c;
        }
    }
    return 0;
}

/* Modifiers arrive as a flags-changed event carrying the new mask rather than
   as key presses, so the edges are recovered by comparing against the last. */
static void update_modifiers(unsigned long flags)
{
    unsigned long changed = flags ^ modifiers;

    if (changed & NS_FLAG_CONTROL)
    {
        queue_key((flags & NS_FLAG_CONTROL) != 0, KEY_FIRE);
    }
    if (changed & NS_FLAG_SHIFT)
    {
        queue_key((flags & NS_FLAG_SHIFT) != 0, KEY_RSHIFT);
    }
    if (changed & NS_FLAG_OPTION)
    {
        queue_key((flags & NS_FLAG_OPTION) != 0, KEY_LALT);
    }
    modifiers = flags;
}

static void post_mouse(void);

static void pump_events(void)
{
    for (;;)
    {
        id event = SEND4(id, app, SEL_("nextEventMatchingMask:untilDate:inMode:dequeue:"),
                         unsigned long, id, id, long,
                         (unsigned long) -1, (id) 0, run_loop_mode, 1);
        long type;

        if (event == 0)
        {
            return;
        }

        type = SEND0(long, event, SEL_("type"));
        if (type == NS_KEY_DOWN || type == NS_KEY_UP)
        {
            unsigned short code = (unsigned short) SEND0(unsigned short, event, SEL_("keyCode"));
            id characters = SEND0(id, event, SEL_("charactersIgnoringModifiers"));
            const char *utf8 = 0;

            if (characters != 0)
            {
                utf8 = SEND0(const char *, characters, SEL_("UTF8String"));
            }
            queue_key(type == NS_KEY_DOWN, translate_key(code, utf8));
            /* Not forwarded: with no responder chain a key event would beep. */
            continue;
        }
        if (type == NS_FLAGS_CHANGED)
        {
            update_modifiers(SEND0(unsigned long, event, SEL_("modifierFlags")));
            continue;
        }
        if (type == NS_MOUSE_MOVED || type == NS_LEFT_MOUSE_DRAG ||
            type == NS_RIGHT_MOUSE_DRAG || type == NS_OTHER_MOUSE_DRAG)
        {
            mouse_dx += SEND0(double, event, SEL_("deltaX"));
            mouse_dy += SEND0(double, event, SEL_("deltaY"));
            continue;
        }
        /* Bit 0 left, bit 1 right, bit 2 middle -- the order Doom expects. */
        if (type == NS_LEFT_MOUSE_DOWN)   { mouse_buttons |= 1; continue; }
        if (type == NS_LEFT_MOUSE_UP)     { mouse_buttons &= ~1; continue; }
        if (type == NS_RIGHT_MOUSE_DOWN)  { mouse_buttons |= 2; continue; }
        if (type == NS_RIGHT_MOUSE_UP)    { mouse_buttons &= ~2; continue; }
        if (type == NS_OTHER_MOUSE_DOWN)  { mouse_buttons |= 4; continue; }
        if (type == NS_OTHER_MOUSE_UP)    { mouse_buttons &= ~4; continue; }
        SEND1(id, app, SEL_("sendEvent:"), id, event);
    }
}

/* Doom Generic's platform interface carries keys only, so the mouse is handed
   to the engine the way its own backends do: as an ev_mouse posted directly.
   data2 turns and data3 moves, with y inverted to match the screen axis. */
static void post_mouse(void)
{
    event_t event;

    if (mouse_dx == 0.0 && mouse_dy == 0.0 && mouse_buttons == last_buttons)
    {
        return;
    }
    event.type = ev_mouse;
    event.data1 = mouse_buttons;
    event.data2 = (int) (mouse_dx * 8.0);
    event.data3 = (int) (-mouse_dy * 8.0);
    event.data4 = 0;
    D_PostEvent(&event);

    last_buttons = mouse_buttons;
    mouse_dx = 0.0;
    mouse_dy = 0.0;
}

/* --- the Doom Generic platform interface -------------------------------- */

void DG_Init(void)
{
    CGRect_t frame;
    id view;
    id nearest;

    memset(key_queue, 0, sizeof(key_queue));
    start_ms = now_ms();

    app = SEND0(id, CLS("NSApplication"), SEL_("sharedApplication"));
    /* NSApplicationActivationPolicyRegular: a real windowed app. */
    SEND1(id, app, SEL_("setActivationPolicy:"), long, 0);

    frame.x = 200.0;
    frame.y = 200.0;
    frame.w = (double) DOOMGENERIC_RESX;
    frame.h = (double) DOOMGENERIC_RESY;

    window = SEND0(id, CLS("NSWindow"), SEL_("alloc"));
    window = ((id (*)(id, SEL, CGRect_t, unsigned long, unsigned long, long))objc_msgSend)(
                 window, SEL_("initWithContentRect:styleMask:backing:defer:"),
                 frame, NS_TITLED | NS_CLOSABLE | NS_MINIATURIZABLE, NS_BACKING_BUFFERED, 0);
    if (window == 0)
    {
        printf("doom: could not create a window\n");
        return;
    }

    view = SEND0(id, window, SEL_("contentView"));
    SEND1(id, view, SEL_("setWantsLayer:"), long, 1);
    SEND1(id, window, SEL_("makeKeyAndOrderFront:"), id, (id) 0);
    SEND1(id, app, SEL_("activateIgnoringOtherApps:"), long, 1);
    SEND0(id, app, SEL_("finishLaunching"));

    layer = SEND0(id, view, SEL_("layer"));
    /* Doom is 320x200 upscaled; keep the pixels crisp instead of blurred. */
    nearest = SEND1(id, CLS("NSString"), SEL_("stringWithUTF8String:"), const char *, "nearest");
    SEND1(id, layer, SEL_("setMagnificationFilter:"), id, nearest);
    SEND1(id, layer, SEL_("setMinificationFilter:"), id, nearest);

    run_loop_mode = SEND1(id, CLS("NSString"), SEL_("stringWithUTF8String:"),
                          const char *, "kCFRunLoopDefaultMode");

    /* Report motion continuously, and decouple the cursor so it neither drifts
       out of the window nor bounds against the edge of the screen. */
    SEND1(id, window, SEL_("setAcceptsMouseMovedEvents:"), long, 1);
    CGAssociateMouseAndMouseCursorPosition(0);
    SEND0(id, CLS("NSCursor"), SEL_("hide"));
}

void DG_DrawFrame(void)
{
    void *space;
    void *context;
    void *image;

    pump_events();
    post_mouse();

    if (layer == 0)
    {
        return;
    }

    space = CGColorSpaceCreateDeviceRGB();
    context = CGBitmapContextCreate(DG_ScreenBuffer, DOOMGENERIC_RESX, DOOMGENERIC_RESY,
                                    8, DOOMGENERIC_RESX * 4, space, DG_BITMAP_INFO);
    if (context != 0)
    {
        image = CGBitmapContextCreateImage(context);
        SEND1(id, layer, SEL_("setContents:"), id, (id) image);
        CGImageRelease(image);
        CGContextRelease(context);
    }
    CGColorSpaceRelease(space);
}

void DG_SleepMs(uint32_t milliseconds)
{
    usleep(milliseconds * 1000);
}

uint32_t DG_GetTicksMs(void)
{
    return now_ms() - start_ms;
}

int DG_GetKey(int *pressed, unsigned char *key)
{
    unsigned short entry;

    if (key_read == key_write)
    {
        return 0;
    }
    entry = key_queue[key_read];
    key_read = (key_read + 1) % KEYQUEUE_SIZE;
    *pressed = (entry >> 8) != 0;
    *key = (unsigned char) (entry & 0xff);
    return 1;
}

void DG_SetWindowTitle(const char *title)
{
    id string;

    if (window == 0)
    {
        return;
    }
    string = SEND1(id, CLS("NSString"), SEL_("stringWithUTF8String:"), const char *, title);
    SEND1(id, window, SEL_("setTitle:"), id, string);
}

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);
    for (;;)
    {
        doomgeneric_Tick();
    }
    return 0;
}
