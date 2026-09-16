# Yabai as the default window manager

Yabai is the current default. It manages windows; skhd handles shortcuts.
Raycast continues to launch apps. AeroSpace is installed and configured as a
fallback, with its own automatic startup disabled in both display profiles.

## Temporary macOS 27 compatibility build

As of September 14, 2026, this Mac runs a locally patched yabai 7.1.25 through
`~/Applications/Yabai macOS 27.app`. The original Homebrew binary is preserved.
This workaround is temporary: return to the official release when it fixes
SIP-enabled Space switching and the macOS 27 window-management paths.

See [the patch record and official-release migration steps](yabai-patches/README.md)
for the exact upstream commits, permission setup, installed paths, validation,
rollback command, and cleanup list. `yabai --version` alone cannot distinguish
the local build because both report 7.1.25.

## Switch now and at future logins

From this checkout, use:

```sh
./wm.sh default yabai       # Use Yabai now and after login/restart
./wm.sh default aerospace   # Switch back if Yabai's behavior or performance is poor
./wm.sh default status      # Show the saved login choice
```

For a temporary comparison, `./wm.sh aerospace` and `./wm.sh yabai` change only
the current session. The saved default returns at the next login. No logout is
needed to switch managers after the initial macOS Spaces setup below.

`default` verifies that the selected manager starts before saving the choice.
It installs one job, `~/Library/LaunchAgents/local.dotfiles.desktop.plist`.
This directly runs `switch-display-mode.sh --service yabai` or `--service aerospace`.
The service starts the selected manager once at graphical login, which applies
the pinned display profile. Nothing polls displays afterwards; pick a profile from
the bar menu or `./wm.sh profile NAME` (auto, docked, single, laptop). A failed
initial manager startup stops the service and records the error.

The installer unloads and archives the former `local.dotfiles.wm-login` and
`com.user.display-mode-switcher` jobs. `./setup-display-switcher.sh --auto` uses
the same installer and preserves the saved manager, so it cannot recreate a
second periodic job. `./wm.sh default install` repairs the service the same way.
SIP stays enabled. Keep AeroSpace's `start-at-login` false even when it is the
selected default, so only this service controls startup.
See [BACKGROUND-SERVICES.md](BACKGROUND-SERVICES.md) for the service inventory.

If startup fails, inspect `~/.local/state/dotfiles-wm/login.err.log` and the
`yabai.err.log` / `skhd.err.log` files beside it. Run `./wm.sh doctor`, or switch
back with `./wm.sh default aerospace`. To remove login startup and periodic
display checks while leaving the current manager running, use `./wm.sh default off`.

The launcher refers to this checkout's absolute path. After moving the checkout,
rerun `./wm.sh default yabai` or `./wm.sh default aerospace` from its new location.

## Plan and first installation

Run these commands from this checkout:

```sh
./wm.sh install
./wm.sh doctor
```

`install` uses `Brewfile.yabai` to install yabai, skhd, jq, and Stow, then links
the two configuration packages into `~/.config`. On Homebrew versions with
package trust, it trusts only the yabai and skhd formulae from `asmvik/formulae`.
It also builds `~/Applications/Dotfiles Spaces.app` using Xcode Command Line
Tools. This short-lived helper creates missing desktops through Mission Control.
It starts neither daemon.
Stow checks conflicts before linking and never adopts or overwrites existing
configuration files. Resolve any reported conflict before retrying.

Yabai must be **7.1.25 or newer** for the SIP-enabled Space operations used here.
The script checks the installed version before quitting AeroSpace.

### One-time macOS preferences

Yabai requires **Displays have separate Spaces** to be enabled. Your existing
AeroSpace setup had it disabled when this configuration was prepared.

```sh
./wm.sh prepare
```

This saves the old values, enables separate Spaces, and disables automatic
Space rearrangement. **Log out and log back in before starting yabai.** The
script never logs you out. A preference read cannot establish whether the
logout has happened, so do not skip this step just because `doctor` shows 0.

Both managers can use the enabled setting, so later switches do not each need
a logout. The preference is retained when switching to AeroSpace. To return to
the original macOS preferences after the trial:

```sh
./wm.sh aerospace
./wm.sh restore-preferences
# Log out and log back in to apply the restored Spaces setting.
```

### Start the trial

```sh
./wm.sh yabai
```

This quits AeroSpace, waits for it to exit, starts yabai and skhd, then reloads
SketchyBar with native Space indicators. Your existing AeroSpace poller exits
when AeroSpace quits. The display-profile switcher follows the active manager.
The physical arrangement repair remains specific to AeroSpace.

On the first attempt, macOS may request Accessibility access. Grant **both**
yabai and skhd access in System Settings > Privacy & Security > Accessibility.
If needed, add their executables using the paths from `command -v yabai` and
`command -v skhd`. Restart with `./wm.sh yabai` after granting access. A failed
startup stops the trial and reopens AeroSpace if it was previously running.

The trial uses jobs named `local.dotfiles.yabai` and `local.dotfiles.skhd`.
Do not also run `brew services start`, `yabai --start-service`, or
`skhd --start-service`; the switcher refuses independently managed instances.
Use `wm.sh` for switching instead of opening both window managers manually.

### Automatic desktops and monitor preferences

`./wm.sh yabai` creates missing desktops automatically, then assigns the
workspace shortcuts. Both managers and both SketchyBar profiles use one policy:

| Active screens | Workspace placement |
|---|---|
| Laptop only, or one external with lid closed | 1–6 on the only screen |
| Laptop + one external | Laptop: 1/3/5; external: 2/4/6 |
| Two externals, lid closed | Preferred odd monitor: 1/3/5; preferred even monitor: 2/4/6 |
| Two externals + laptop | Same external assignments; laptop: 7/8/9 |

Edit **`yabai/.config/yabai/display-preferences.json`** to change monitors:

```json
{
  "odd_monitor": "LG HDR QHD",
  "even_monitor": "PA278QV"
}
```

These variables are exact macOS display names, shared by AeroSpace and yabai.
Run `yabai/.config/yabai/scripts/display-layout.sh --aerospace` while AeroSpace
is active, or omit `--aerospace` while yabai is active, to see detected names
and assignments. With only one external connected it always gets 2/4/6,
regardless of its preferred role. Unknown pairs fall back to physical left-to-right
order; a recognized monitor keeps its preferred role.

After editing, run `./switch-display-mode.sh` or pick the profile again from the
bar menu. Workspace roles do not depend on which display is main.
The optional `clamshell_repair` section holds the older AeroSpace physical-layout
snapshot. On replacement hardware, set its `enabled` to `false`, or update its
UUIDs/settings from `displayplacer list` if you want arrangement repair too.

Existing native desktops and windows are preserved; extra desktops are never
deleted. Fullscreen and custom-labelled desktops do not count toward the target.

**One-time permission:** enable **Dotfiles Spaces** in System Settings > Privacy
& Security > Accessibility. If needed, add `~/Applications/Dotfiles Spaces.app`
with the `+` button. This is separate from yabai and skhd's permissions. macOS
may ask again if the locally built helper changes or you reinstall it.
Open the helper from Finder to request access explicitly. Automated desktop
setup checks permission without opening a dialog. If access is unavailable
during hotplug, the display profile still updates SketchyBar, yabai padding,
and labels for existing desktops. It leaves missing desktops for `./wm.sh spaces`
after permission is restored, without repeating setup on every display check.

The helper keeps SIP enabled. When desktops are missing, it briefly opens Mission
Control and presses the Add Desktop button on the appropriate physical display,
then checks yabai's desktop count after each click. If all desktops already exist,
it does not open Mission Control. Startup stops and reports an error if setup
fails; it restores AeroSpace if AeroSpace was running before the attempt.

After granting permission, retry `./wm.sh yabai`. While the trial is already
running, retry desktop setup with `./wm.sh spaces` or click a gray bar slot.
`./wm.sh reload` also repairs missing desktops.

Yabai assigns `ws1`–`ws9` to ordinary desktops on the planned displays and
reassigns these owned labels after hotplug. Custom labels are preserved. With SIP
enabled, this changes desktop numbers without relocating whole native Spaces or
their existing windows. AeroSpace moves its own workspaces to the planned monitors.
When the laptop disappears, 7–9 leave the default bar; extra native desktops remain
accessible in Mission Control and are shown as `D<number>` in the yabai bar.

The helper uses Mission Control's Accessibility identifiers, which Apple can
change between macOS releases. Its Swift source and build script are tracked in
the dotfiles; the compiled app stays outside Git.

New managed windows open on the focused display's current workspace.
New Warp, PyCharm, GitHub Desktop, and Slack windows also receive keyboard focus.
These apps have no fixed workspace assignment in yabai. Opening an app that
already has a window elsewhere can still activate that existing window;
this setting does not bring existing windows to the current workspace.
AeroSpace keeps its own app assignments.

## Switch back

```sh
./wm.sh default aerospace
```

This changes the login default, stops the yabai/skhd jobs, verifies they have
exited, opens AeroSpace, reloads its SketchyBar items, and resumes the display
profile switcher.
The AeroSpace configuration is preserved. Extra native desktops remain, and
the previous window positions and AeroSpace workspace assignments are not
restored from a snapshot. Use Mission Control to gather windows into your usual
desktop on each display and remove unneeded empty desktops yourself.

## Shortcuts

### Shortcut help

Enter service mode with **Cmd + Alt + S** or **F14**, then press **?**
(**Shift + /**) to open the shortcut popup below the SERVICE badge. Press ?
again to hide it, or click the badge to toggle it. **Escape**, **Space**, or
**F15** closes the popup and returns to normal mode.

The popup separates service-mode keys from normal-mode shortcuts and shows the
commands for the active manager. Normal-mode shortcuts require leaving service
mode first. Both docked and undocked profiles include the same help behavior.

### Key bindings

Both AeroSpace profiles use the same shortcut map. Their shared shortcuts also
match skhd, including Cmd + Alt + S / F14 for service mode, Escape / Space / F15
to exit service mode, keypad workspace keys, and Cmd + Ctrl + arrows to move
the selected window between monitors. Cmd + G is available to applications.

| Shortcut | yabai action |
|---|---|
| Cmd + arrow | Focus neighboring window, continuing across monitors |
| Cmd + Shift + arrow | Swap, fill the side, then move to the neighboring monitor |
| Cmd + 1–9, including keypad | Focus labelled desktop |
| Cmd + Shift + 1–9 | Send window to desktop and follow it |
| Cmd + Ctrl + Shift + 1–9 | Send window to desktop and stay on the current workspace |
| Cmd + Page Up / Page Down | Previous / next native Space |
| Cmd + Home / End | Workspace 1 / 6 |
| Alt + Tab | Previous focused Space |
| Ctrl + Tab | Toggle between current and previously focused window |
| Cmd + Ctrl + left / right | Send window to previous / next display, wrapping |
| Cmd + equals / minus | Resize width |
| Cmd + Shift + equals / minus | Resize height |
| Cmd + 0 or Cmd + Ctrl + 0 | Balance all tiled window sizes in the current workspace |
| Cmd + Ctrl + equals / minus | Step column width up / down through 50%, 65%, 75% |
| Cmd + F | Fill the tiling area without native fullscreen |
| Cmd + J | Toggle the focused window's split direction |
| Cmd + comma | Toggle whole-Space BSP / stack layout |
| Cmd + Ctrl + Shift + F | Float / tile; restore the saved floating size and position |
| Cmd + Ctrl + Alt + Shift + D | Restore BSP layout and balance windows |
| Cmd + Ctrl + Alt + Shift + R | Resize mode; arrows resize, Shift uses larger steps |
| Cmd + Ctrl + Alt + Shift + W | Workspace/display navigation mode |
| Cmd + Ctrl + Alt + Shift + M | Insertion mode; arrows choose where the next window goes |
| Cmd + Alt + S or F14 | Service mode; F toggles floating and exits, R balances, up/down changes volume |
| Escape / Space in a mode | Return to normal shortcuts |
| Alt + Shift + C | Reload yabai rules and skhd shortcuts |

BSP is yabai's binary split layout. Stack is not AeroSpace accordion, and
insertion is not AeroSpace container merging. Directional focus and previous/next
Space navigation stop at boundaries; only the display-send helper wraps.
Modes stay active until Escape/Space, or F15 in service mode. The old
close-all-other-windows action is not bound in this trial.

Switching a yabai workspace also checks window focus. If macOS leaves Finder or
another workspace active, the helper focuses a visible window in the destination.
An existing valid selection is preserved, floating windows are eligible, and
empty workspaces remain empty. This covers keyboard shortcuts, bar clicks, and
native Space/display-change events.

### Floating size and position

Float shortcuts in both managers remember each window's last floating size and
position when you tile it. Floating it again restores that geometry. Moving it
to another monitor translates and clamps the saved frame to the current screen.
A new window keeps the existing centered default size until you save a floating
position. Memory belongs to that window, not every future window of the app.

Use **Cmd + Ctrl + Shift + F**, or enter service mode and press **F**. Service F
returns to normal mode immediately in both managers, whether floating or tiling.
The SERVICE badge and help popup close too.

The cache lives in `~/.local/state/dotfiles-wm/float-frames.json`, holds at most
200 windows, and is shared between the two implementations. No polling or
background process is added. Yabai uses its existing socket transport; AeroSpace
uses one Accessibility script invocation per toggle.

### Previous window

**Ctrl + Tab** returns to the last focused window. Press it again to
return to the window you just left. This works with different applications or
two windows of the same application, including floating windows and windows on
other monitors. The yabai helper remembers the last two windows from focus
events so floating windows are eligible too. It has no polling loop or daemon.
It changes focus without rearranging windows or moving the pointer.
When the target is on an inactive Space, yabai explicitly activates that Space
first, using the same switch command as Cmd + number, then focuses the window.

AeroSpace uses its built-in focus history and can also return to an
empty workspace, and closing the previous window can leave no target to return
to. Focus two open windows to establish a new pair. **Alt + Tab** remains the
separate previous-workspace shortcut. Yabai starts a new pair when its config is
reloaded and skips closed, hidden, or minimized targets.

### Column width presets

For small adjustments, Cmd + equals / minus changes width and adding Shift
changes height. Yabai's `wm-resize.py` selects the shared divider from the tile
order, including a containing column when the selected window is in a row.
It does not probe the outer edge first: yabai's pixel rounding can misidentify
that edge and reverse the resize direction. Resize mode uses the same helper.
Floating windows resize from their bottom-right corner; app minimum sizes still
apply. These commands do not change focus.

Cmd + Ctrl + equals increases the selected column to the next preset;
Cmd + Ctrl + minus decreases it. The presets are 50%, 65%, and 75% of the
two columns' combined width, excluding the gap. They stop at the endpoints
and use the actual width, so manual resizing and Cmd + 0 remain compatible.
Change `PRESETS` in `wm-size.py` to customize the sizes for both managers.

This preserves the two-column layout, including multiple windows stacked in
either column. The focused window stays selected. Floating, fullscreen,
accordion/stack layouts, and layouts with more or fewer than two aligned
columns are left alone. App minimum widths can limit shrinking. Yabai calculates
the split from column positions, the configured gap, and the display edge, so
an app extending beyond its assigned tile does not disable the presets.
The helper runs only on a keypress; yabai uses the existing native socket.
AeroSpace reads window geometry on demand. No background watcher is added.

### Directional focus and movement

In both managers, **Cmd + Shift + arrow** first swaps the selected tiled window
with a neighbor without changing the tile sizes. At the workspace edge, pressing
toward that edge gives the selected window its own side, with the other windows
grouped opposite it. Right/left makes a full-height column; up/down makes a
full-width row. Once the window fills that side, another press moves it to the
neighboring monitor's visible workspace and follows it. A window already filling
the side crosses immediately, including two side-by-side windows or a sole window.
With no monitor in that direction, it stays put. These shortcuts never wrap around.

For example, select the bottom-right window in a three-window layout and press
Cmd + Shift + Right. It fills the right half and the other two share the left.
Press Right again to move it to the monitor on the right, if one is connected.
Yabai leaves floating/fullscreen/zoomed windows and deliberate stacks alone.
AeroSpace uses its swap command and rebuilds the tiling group on an edge press.

**Cmd + arrow** changes focus without moving or resizing windows. At an edge,
it continues onto the adjacent monitor. Both movement and focus enter from the
near side: moving left enters the right edge of the left monitor, and moving
right enters the left edge of the right monitor. Up/down follows the same rule.
An arriving tiled window gets a full side of the destination, with the existing
windows grouped opposite it. In yabai, that group is balanced so repeated moves
do not produce progressively smaller tiles. Movement waits for macOS to report
the destination before arranging it.
Focus prefers the same row or column when multiple windows share the incoming
edge. An empty destination monitor receives focus without opening an application.
Arrow selection also handles partially overlapping windows when an app refuses
to shrink to its assigned tile size.
Window, workspace, and monitor focus changes keep the pointer in place in
yabai and both AeroSpace profiles. This applies to keyboard shortcuts and
SketchyBar clicks, with either docked or undocked bars. No click override is
needed.

The shared `wm-direction.py` helper uses the current window sizes and physical
monitor arrangement. AeroSpace reads window bounds through macOS CoreGraphics;
it does not require yabai to be running.

Focus shortcuts use a separate lock from window moves and size presets. An app
that delays or refuses a requested size cannot make the layout helper discard
Cmd + arrow presses. Repeated focus commands still run one at a time.

For yabai, the helper sends commands directly to its local socket to avoid
starting a separate CLI process for every operation. It falls back to the CLI
if it cannot connect, and never retries a move after a request has been sent.
Balanced two- and three-window layouts reuse their existing tiles with swaps
and, when needed, a mirror or rotation. Simple swaps and these layout changes
finish when the requested window bounds arrive, without fixed settling delays.
If an app enforces a minimum size, the helper accepts its actual size after
100 ms without further changes, provided every window reached its expected
position. This also handles the replacement app shrinking below the previous
occupant's minimum size. Previously T3 refused a 523-point tile and stayed at
620 points, causing a one-second timeout that discarded subsequent move keys.
The reproduced swap fell from 1.03 seconds to approximately 0.13 seconds.
The regrouping path also accepts stable overlapping tiles with distinct origins
after four samples, so minimum sizes do not force another one-second timeout.
Moving frames, wrong positions, and windows disappearing still prevent further
layout operations.
More complex layouts retain the general regrouping path, so they can still show
intermediate redraws. No window animation is enabled by this helper.

### Raycast

Cmd+Space, your main Raycast shortcut, is left unbound. The screenshot supplied
during setup confirms these existing Raycast shortcuts; none conflicts with skhd:

| Raycast action | Reserved shortcut |
|---|---|
| Cursor | Cmd + Shift + C |
| Finder | Cmd + Shift + E |
| GitHub Desktop | Cmd + Shift + G |
| Google Chrome | Cmd + Shift + B |
| PyCharm | Cmd + Shift + P |
| Slack | Cmd + Shift + S |
| VLC | Cmd + Shift + V |
| Warp | Cmd + Return |
| Zen | Cmd + Shift + Z |
| Open Docker Desktop | Cmd + Shift + D |
| MRS quicklink | Alt + Shift + M |
| Search Emoji & Symbols | Ctrl + Cmd + Space |

Automated checks reserve these combinations in all skhd modes and ensure its
global combinations are a subset of the existing docked AeroSpace bindings.
Modes do not capture unbound keys. Raycast keeps app launching; skhd adds no
app-launch shortcuts. When adding shortcuts later, keep each combination assigned
in only one app, including Hyper combinations generated by your keyboard.

If skhd stops receiving keys inside a terminal, check its Secure Keyboard Entry
setting. That macOS feature prevents global keyboard listeners from receiving
the events; changing Raycast's shortcuts will not fix it.

## SketchyBar and borders

On macOS 27, the regular and docked profiles use normal SketchyBar items for
CodexBar and Amphetamine because their native menu windows are absent from
SketchyBar's alias lookup. `scripts/menu-status.py` reads CodexBar's displayed
percentages through Accessibility and opens the provider menus. Amphetamine
keeps its session controls and shows a coffee icon colored by its current state.
CodexBar's separate provider icons must remain enabled. Missing status reads
show `?` rather than a stale percentage. Older macOS versions keep the aliases.
These SketchyBar changes are independent of the temporary yabai build.

The existing regular and docked Lua themes select yabai items while the trial
job exists. The replacement shows desktop numbers, app icons, focused desktop,
and the active skhd mode. All configured slots stay visible on their assigned
monitors, including laptop slots 7–9 with both externals connected. Gray slots
mean the native desktop does not exist yet: clicking one retries automatic setup.
Clicking an existing desktop selects it. Native desktop/window
events and yabai signals update the bar without the AeroSpace polling workaround.

A purple `SERVICE` badge appears immediately after the workspace group on every
monitor while service mode is active, in both the yabai and AeroSpace profiles.
It hides on exit and restores its state after a bar reload. AeroSpace uses its
mode-change callback; skhd records the mode for its current daemon process.

Right-side widgets and the center app indicator use the existing theme. The
shared module joins yabai and SketchyBar displays by their physical display IDs,
so their differing arrangement indices do not pin the indicators to the wrong
screen. Missing displays hide affected items until a complete update arrives.

The yabai config applies the current theme's JankyBorders colors and width on
startup and reload, with purple/gray defaults when no theme is installed.
JankyBorders remains optional. Initial top padding is
50 points, then the display profile applies `built_in_top_padding` (16) or
`external_top_padding` (50) from the shared preferences. AeroSpace has matching
per-monitor gaps in its TOML files. The separate `sketchybar-light` profile is not
integrated by this setup.

## Reinstall or move to another Mac

Clone this repository wherever you prefer, then run `./wm.sh install` there.
The new packages and helpers use the current home directory and support both
Homebrew prefixes. Workspace assignment needs only your monitor names. The
optional physical-layout repair snapshot is machine-specific; disable it or
update it on the new Mac.

For switching back on a fresh Mac, install AeroSpace and link the appropriate
existing AeroSpace package. To reproduce the bar, install SketchyBar and its
SbarLua dependencies and link your regular or docked SketchyBar package as usual.
The trial does not install or replace your entire desktop setup. The older
display-profile scripts still assume the repository lives at `~/dotfiles`.

Tracked files:

- `Brewfile.yabai`: optional package dependencies.
- `wm.sh`: installation, preferences, switching, rollback, and diagnostics.
- `wm-startup.py`: saved login selection and LaunchAgent installation.
- `yabai/.config/yabai/display-preferences.json`: shared monitor roles and optional physical repair.
- `yabai/.config/yabai/yabairc`: tiling, gaps, floating rules, and event signals.
- `yabai/.config/yabai/scripts/`: desktop setup, workspace labels, and window helpers.
- `yabai/.config/yabai/helpers/Spaces.swift`: SIP-enabled desktop creation helper.
- `yabai/.config/yabai/sketchybar.lua`: shared native Space bar items.
- `skhd/.config/skhd/skhdrc`: keyboard shortcuts and modes.

After edits, run `./wm.sh reload`. Logs and saved preferences live in
`~/.local/state/dotfiles-wm/`, outside Git. Installation can be repeated without
adopting existing files. To unlink the trial configs after returning to AeroSpace:

```sh
stow --dir="$PWD" --target="$HOME" -D yabai skhd
```

## Validation

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
lua tests/test_yabai_bar.lua "$PWD"
lua tests/test_service_mode.lua "$PWD"
```

These tests simulate the desktop commands. They check failure recovery,
mutually exclusive managers, label assignment, one/two/three-screen profiles,
retry/no-op behavior, and SketchyBar rendering. Live Accessibility permissions, actual keyboard delivery,
hotplug, and rendering still need a manual trial after the one-time logout.

During that trial check: open/close several windows in the same app, move between
all configured desktops, float/resize a window, play Nuvio video, launch apps through
Raycast, unplug/reconnect a monitor, then switch back to AeroSpace.

## Upstream references

- [yabai installation](https://github.com/asmvik/yabai/wiki/Installing-yabai-(latest-release))
- [yabai command reference](https://github.com/asmvik/yabai/blob/master/doc/yabai.asciidoc)
- [yabai SIP requirements](https://github.com/asmvik/yabai/wiki/Disabling-System-Integrity-Protection)
- [skhd configuration](https://github.com/asmvik/skhd) — the original skhd is in maintenance mode.
- [SketchyBar events](https://felixkratz.github.io/SketchyBar/config/events)

### Floating position and size

Float → tile saves the window's latest floating frame. Floating it again restores
that position and size on the same monitor. Moving to a smaller display keeps the
window reachable by fitting it within the available area. An app's own minimum
size can prevent an exact fit; the helper reports that instead of silently
claiming success.

The helper waits for the move to update before resizing. Yabai's move operation
uses a cached full frame, so a move sent immediately after resize could restore
the old tiled dimensions. No background watcher is added. A targeted live recheck
passed six exact restores at two custom positions and sizes; total restore calls
took about 66–70 ms. See [recorded check data](reports/float-restoration-2026-09-16.json).

### Monitor movement failure recovery

Cmd+Shift+arrow keeps the swap → expand → cross sequence. Crossing right enters
on the destination's left side; crossing left enters on its right side. The moved
window receives focus before destination rearrangement begins.

Space queries can include non-AX windows that yabai cannot manipulate. Movement
and the shared resize policy exclude these records. Failed warps clear their
insertion hint, preventing a stuck red overlay and unintended later insertion.
This adds no background worker or polling. The separate Cmd+Ctrl+arrow monitor
send also follows the moved window by ID.

The [September 16 movement check](reports/monitor-movement-2026-09-16.json) passed
16 crossings and four swap/expand checks with disposable windows. Four-window
BSP rebuilding still took 0.6–1.2 seconds; this fix addresses failure recovery,
not that existing layout cost.
