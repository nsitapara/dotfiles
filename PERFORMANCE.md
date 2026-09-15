# Window-manager and bar performance

Measured on this Mac, macOS 27.0 build 26A428, on 2026-09-14. These are local
wall-clock samples, not guarantees for other machines or busy applications.

| Operation | Before | After |
| --- | --- | --- |
| Focus helper, correct destination window already selected | 133 ms median, 5 runs | 32 ms median, 8 runs |
| Amphetamine idle hover subprocesses | 60/minute | 0 on macOS 27 |
| Amphetamine idle power checks | 60/minute | 12/minute on macOS 27 |

The focus helper now uses the same direct yabai socket transport as directional
shortcuts. It immediately returns when focus is already correct. Repairs still
wait 80 ms for Space activation and re-check the active Space before focusing a
window, so late events cannot pull the user back to an old desktop.

The regular Amphetamine item uses SketchyBar mouse entry/exit events. Its closed
widget checks power assertions every five seconds; an open tooltip refreshes
every second. Clicks and power/wake events still update immediately. Slow power
queries cannot overlap. Older macOS alias items retain pointer polling because
image refreshes can produce unreliable mouse exit events.

## Why keep Python

Python is used for short control scripts, not for rendering the bar or tiling
windows. Apple Python startup measured 18 ms; loading the directional helper
through `--help` measured 35 ms. An individual yabai query measured 6.7 ms through
the CLI and 1.5 ms through its socket. Reusing the socket and avoiding an
unconditional sleep saved more than replacing the interpreter could save here.

The earlier T3 move stall was a different problem: its minimum window height
made an exact-frame wait impossible. Commit `d10149a` accepts settled frames at
the requested positions. The reproduced move fell from about 1.03 seconds to
0.13 seconds. See `YABAI.md` for the minimum-size behavior.

CodexBar status readout measured 140 ms including AppleScript, once every five
seconds. It already combines both providers and suppresses overlapping requests.
The native Swift menu-hover helper polls the pointer at 30 Hz and menu window
metadata at 10 Hz. That existing scan implements native-menu hide/show. Python
only builds/launches the helper and then replaces itself with the Swift process.

## Blank bar clicks

The dimming issue reproduces with a minimal native SketchyBar bar without any
of these scripts. A click raises the background over item windows at the same
window level. See [the native fix and official-release rollback](sketchybar-patches/README.md).
The attempted scan-and-reorder recovery was removed. The native patch prevents
the ordering problem and adds no polling, sleeps, or per-click processes.

Validation includes 80 window-manager tests under Homebrew Python, 12 workspace
focus tests under Apple Python, and Lua widget lifecycle checks for both profiles
and both OS paths. Live checks covered widget hover entry/exit, repeated blank
clicks, and native menu hide/show. Tests requiring `tomllib` need Python 3.11+;
the runtime helpers remain compatible with Apple's Python 3.9.
