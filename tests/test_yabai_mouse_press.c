// Validate the local yabai patch that keeps yabai's own retiling from being
// read as a mouse resize or drop. Pure logic; no events are posted.
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <CoreGraphics/CoreGraphics.h>
#include "misc/mouse_press.h"

int main(void)
{
    // One tick per millisecond keeps the table readable.
    const uint64_t freq = 1000, down = 100000;
    const struct {
        const char *name;
        CGPoint up;
        uint64_t layout_time;
        bool layout;
    } cases[] = {
        {"click, never retiled",                 {100, 100}, 0,            true},
        {"click with jitter",                    {103, 101}, 0,            true},
        {"click on a window yabai just placed",  {100, 100}, down - 200,   true},
        {"drag, never retiled",                  {150, 100}, 0,            false},
        {"drag, retiled long before the press",  {150, 100}, down - 5000,  false},
        {"drag, placement still landing",        {150, 100}, down - 200,   true},
        {"drag, retiled during the press",       {150, 100}, down + 300,   true},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i) {
        bool layout = mouse_press_frame_change_is_layout((CGPoint){100, 100}, cases[i].up, down, cases[i].layout_time, freq);
        if (layout != cases[i].layout) {
            fprintf(stderr, "FAIL: %s\n", cases[i].name);
            return 1;
        }
    }
    puts("Mouse press guard passed for clicks, user drags, and drags over yabai retiles.");
    return 0;
}
