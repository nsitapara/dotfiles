# Window manager switching and Rift

Yabai is the behavior reference. Rift is an optional trial while cross-monitor,
native-fullscreen and layout parity checks are completed. A performance comparison
must follow those checks; lower CPU use alone does not qualify a replacement.

## Choose a manager

Click the monitor icon in SketchyBar, then **Use yabai**, **Use AeroSpace**, or
**Use Rift**. The label combines the monitor profile count and the active manager:
`2` for yabai, `2 A` for AeroSpace, or `2 R` for Rift. `2 Off` means no manager is active. The highlighted menu row shows the active manager.
Menu choices apply to the current session; yabai remains the saved login default.
**Quit window manager** stops the managers and shortcuts, leaves app windows open,
and preserves the login default. The terminal equivalent is `./wm.sh quit`.
Rift virtual windows are revealed before quitting when it responds; an emergency
quit still stops it if its release command is stuck, and reports that limitation.

The same commands work in a terminal:

```sh
./wm.sh use rift
./wm.sh use yabai
./wm.sh use aerospace
./wm.sh use rift --temporary
./wm.sh current
./wm.sh default status
./wm.sh doctor
```

The temporary form leaves the saved login choice alone. The older `./wm.sh rift`,
`yabai`, and `aerospace` forms also switch only the current session.

Switching captures live window IDs, process IDs, numbered workspaces, and floating
state. It stops the current manager before starting another and restores those
assignments where the windows still exist. Window titles are not stored. Native
fullscreen, custom desktops, minimized and hidden windows are excluded from a
yabai handoff. Entire tiling trees are not translated between engines.

Owned launchd jobs use `local.dotfiles.*`. Existing external WM services are
rejected before switching. A failed startup attempts to restore the previous
manager. Logs and private handoff state are in `~/.local/state/dotfiles-wm/`.
The popup writes errors to `menu-switch.log` there.

## Install

```sh
./wm.sh install rift
```

This installs the official [Rift 0.5.9 release](https://github.com/acsandmann/rift/releases/tag/v0.5.9)
archive, verifies its SHA-256 against the official formula, and follows the
formula's ad-hoc signing step. It does not compile a patched Rift or change SIP.
The executable is `~/.local/opt/rift/0.5.9/rift` and commands are linked into
`~/.local/bin`. Stow, jq, skhd, and the Xcode command line tools are required.

Enable that executable in System Settings → Privacy & Security → Device Control
and Data Access. The label may be Accessibility on other macOS versions. skhd
also needs its existing permission. A disabled launchd probe checks Rift's grant
before stopping the current manager. Opening Xcode once may be required after an
Xcode update to complete its setup.

## Shared controls

| Shortcut | Behavior |
| --- | --- |
| Cmd+1–9, including keypad | Focus the numbered workspace |
| Cmd+Shift+number | Move the window and follow it |
| Cmd+Ctrl+Shift+number | Move the window and keep the source workspace |
| Cmd+arrow | Directional focus, continuing across monitors |
| Cmd+Shift+arrow | Swap a neighbor, occupy a side, then cross monitors |
| Cmd+Ctrl+Left/Right | Move to previous/next monitor and follow, with wrapping |
| Cmd+= / Cmd+minus | Width +32 / −32 pixels |
| Cmd+Shift+= / Cmd+Shift+minus | Height +32 / −32 pixels |
| Cmd+Ctrl+= / Cmd+Ctrl+minus | Step a two-column layout through 50%, 65%, 75% |
| Cmd+Ctrl+Shift+F | Float/tile, restoring saved floating geometry |
| Alt+Tab | Previous numbered workspace |
| Ctrl+Tab | Previously focused window, including floating windows |

Both bar profiles use yabai's workspace renderer for Rift, including app icons,
stable app order, and one Chrome icon per window. The display layout and preferred
monitor names are shared in `scripts/wm/display-layout.jq` and
`scripts/wm/display-preferences.json`. Native desktops and Rift's virtual
workspaces use different internal IDs; global numbers stay the same.

The default is BSP with the same 15px inner gaps and monitor-specific outer gaps
as yabai. Floating utility rules match yabai. AeroSpace's old app-to-workspace
assignments were removed to match yabai's current behavior.

## Try Rift's extra layouts

Press **F14** or **Cmd+Alt+S**, then one key:

| Key | Layout/action |
| --- | --- |
| B | BSP, the usual default |
| T | Traditional, Rift's flexible nested splits |
| S | Stack the whole workspace |
| M | Master/stack |
| C | Scrolling columns |
| G | Toggle the selected parent group's stack in flexible splits |
| U | Unjoin in flexible splits |
| ? | Show the shortcut reference |

Layout choices return to normal mode. **Cmd+J** changes split orientation,
**Cmd+,** switches BSP/stack, and **Cmd+F** expands the window within the outer
gaps. In flexible splits, **Ctrl+Alt+Cmd+Shift+M**, then an arrow, joins toward the
neighbor. Escape leaves that mode. Grouping is a Rift feature; it is not yabai's
insertion hint for the next new window.

Cmd+0 rebuilds the workspace as BSP with default sizes. Unlike yabai's balance,
this can change the split structure. Pixel resize and side-expansion adapters
currently target BSP. Other layouts keep their native semantics.

## Current validation limits

The automated suite covers mutual exclusion, six switch directions, startup
failure recovery, display policy, shortcuts and the shared bar. Live tests use
disposable AppKit windows and restore the prior workspaces afterward.

Rift's BSP command only swaps or crosses monitors. Occupying a full side requires
temporarily detaching and reinserting the other tiled leaves. The selected
window stays tiled. This needs latency and visual checks before it can replace
yabai's behavior. Three-window expansion, width resizing, float/tile and
workspace stack/BSP changes have passed live checks. Monitor crossing is still
under validation. Physical unplug/replug, lid transitions and sleep/wake have
not been certified by these tests.

Rift can report `space: null` on a monitor in macOS native fullscreen. The adapter
stops that action and reports the unavailable desktop. Exit native fullscreen
before retrying. It does not force an app out of fullscreen.

## Benchmark acceptance and method

Compare yabai, Rift and AeroSpace only after the same workflow passes. Record
failures alongside timings; never exclude a failed action to improve its score.

Use identical disposable windows on the same two monitors and the same gap,
workspace and animation settings. Warm up each manager, then alternate test
order across repeated runs. Check final focus and window geometry after every
operation, not just the CLI exit status.

Measure workspace and directional-focus latency, neighbor swaps, side expansion,
cross-monitor movement, presets and float/tile. Report median and p95. Separate
idle CPU from CPU used during repeated actions. Include peak and steady resident
memory for the manager, skhd, event subscribers, Python adapters and manager-owned
pollers. Record SketchyBar and WindowServer separately because they are shared.
Record OS, binary versions, monitor geometry and sample duration with results.

The [September 16 report](reports/window-managers-2026-09-16.html) recommends
keeping the established yabai workflow. Its correction explains why most of the
first benchmark cannot support a performance ranking: both Rift rounds and yabai
round 2 placed six fixture windows on workspace 5 instead of three on each monitor.
The earlier pooled 9.3× expansion comparison is therefore not a fair workload
comparison. Rift's visible sequential retiling remains a practical concern.

Yabai round 1 had the intended setup and three unresolved width-preset failures.
Round 2's floating restoration check also needs better evidence. No corrected
live run has been performed; the report retains the raw results and diagnoses
which checks were invalid. AeroSpace is outside the current decision.

The switcher now checks the loaded SketchyBar backend after the handoff, including
when the selected manager is already active. This repairs stale Rift workspace
labels such as `D201` and the old click/event callbacks without creating or
deleting native desktops.

To repeat the benchmark later with an idle keyboard and mouse:

```sh
python3 scripts/benchmark-window-managers.py --run-live --managers yabai rift \
  --rounds 2 --repeats 12 --idle-seconds 30 --output reports/new-run.json
python3 scripts/render-wm-benchmark.py reports/new-run.json
```

The original measurements are retained in the report's adjacent JSON file.
The separate notes file adds interpretations and qualifications without changing
those measurements. A future run should use its own output path.
