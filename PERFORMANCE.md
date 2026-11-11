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

## Stats widgets: one native provider (2026-11-10, macOS 27.2.1)

CPU, memory, SSD and temperature used to run their own timers and shell out:
`iostat` every 2 s (each run blocks for a 1 s sample), `sysctl` + `vm_stat` and
Stats.app's `smc` every 5 s, plus a separate `cpu_load` provider. They now share
one C provider, `helpers/event_providers/system_stats`, which reads the kernel
directly and fires a single `system_stats` event:

| Reading | Source | Cadence |
| --- | --- | --- |
| CPU load | `host_statistics` | 2 s |
| Memory | `host_statistics64` (same app + wired + compressed formula as before) | 2 s |
| Temperature | AppleSMC user client, key `TCMb` (same key Stats.app reads) | 2 s |
| Disk space | `statfs` on `/System/Volumes/Data` | 5 min and on wake |

Readings were checked against the old commands at the same moment: memory 45.0%
vs 45.1% from `vm_stat`, disk 74% from `df`, and `TCMb` 48.3 vs 48.25 from `smc`.

| 60 s idle sample | Before | After |
| --- | --- | --- |
| Sensor commands spawned | 37 | 0 |
| `sbar-hover` CPU | 0.40 s | 0.12–0.28 s (depends on pointer position) |
| SketchyBar daemon CPU | 0.21 s | 0.11 s at 4 s ticks, 0.20 s at 2 s |
| Provider CPU / memory | `cpu_load` 0.00 s | `system_stats` 0.00 s, 5.4 MB, flat |

A forced 0.25 s tick put the cost of one update of all four graphs at about
7.5 ms of daemon + Lua CPU, almost all of it SketchyBar redrawing. The graphs
were later removed: each widget is now an icon and a number coloured by usage
(white, then yellow, orange and red), which redraws less and is about 5-10 pt
narrower per widget. Daemon samples are noisy: window and Space changes also redraw the bar.

The hover helper polls the pointer at 10 Hz while it is more than 200 pt below
the top (30 Hz near the top or during a hand-off), and checks the window list for
keyboard-opened menus at 1 Hz instead of 2 Hz; the native bar draws above
SketchyBar, so the later hide is invisible. The Amphetamine widget's closed-state
power check went from 5 s to 15 s; clicks, power changes and wake still update it
at once.

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
On macOS 27 it reads the `codexbar usage` CLI instead, which measured ~30 s and
0.18 s CPU per fetch (2026-11-10), so it refreshes every 2 minutes in both
profiles (the docked profile had still been on 5 s, keeping the CLI running
almost continuously).
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
