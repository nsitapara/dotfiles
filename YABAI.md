# Try yabai and skhd

This is an optional macOS setup alongside AeroSpace. Yabai manages windows;
skhd handles shortcuts. Raycast continues to launch apps.

The trial keeps SIP enabled. It uses transient launchd jobs for this login,
without installing yabai/skhd login services. AeroSpace's existing login setting
is unchanged. At the next login, use `./wm.sh yabai` to start another trial.

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
when AeroSpace quits. The display-profile switcher and monitor-repair script
pause while the trial job is loaded.

On the first attempt, macOS may request Accessibility access. Grant **both**
yabai and skhd access in System Settings > Privacy & Security > Accessibility.
If needed, add their executables using the paths from `command -v yabai` and
`command -v skhd`. Restart with `./wm.sh yabai` after granting access. A failed
startup stops the trial and reopens AeroSpace if it was previously running.

The trial uses jobs named `local.dotfiles.yabai` and `local.dotfiles.skhd`.
Do not also run `brew services start`, `yabai --start-service`, or
`skhd --start-service`; the switcher refuses independently managed instances.
Use `wm.sh` for switching instead of opening both window managers manually.

### Set up the six desktops

`./wm.sh yabai` creates missing desktops automatically, then assigns the
workspace shortcuts. It keeps six ordinary desktops on one monitor, or three
on each of two monitors. Existing desktops and windows are preserved; extra
desktops are never deleted. Fullscreen app Spaces do not count.

**One-time permission:** enable **Dotfiles Spaces** in System Settings > Privacy
& Security > Accessibility. If needed, add `~/Applications/Dotfiles Spaces.app`
with the `+` button. This is separate from yabai and skhd's permissions. macOS
may ask again if the locally built helper changes or you reinstall it.

The helper keeps SIP enabled. When desktops are missing, it briefly opens Mission
Control and presses the Add Desktop button on the appropriate physical display,
then checks yabai's desktop count after each click. If all desktops already exist,
it does not open Mission Control. Startup stops and reports an error if setup
fails; it restores AeroSpace if AeroSpace was running before the attempt.

After granting permission, retry `./wm.sh yabai`. While the trial is already
running, retry desktop setup with `./wm.sh spaces` or click a gray bar slot.
`./wm.sh reload` also repairs missing desktops.

On one monitor, desktops are labelled `ws1` through `ws6` in native order. On
two monitors, left-to-right display positions determine the mapping: `1,3,5`
on the left and `2,4,6` on the right, matching the docked AeroSpace profile.
Conflicting existing labels are not overwritten. More than two displays need a
custom mapping. Fully established labels are retained across monitor changes;
the helper adds desktops but does not relocate labelled Spaces after hotplug.

The helper uses Mission Control's Accessibility identifiers, which Apple can
change between macOS releases. Its Swift source and build script are tracked in
the dotfiles; the compiled app stays outside Git.

Warp and PyCharm route to `ws1`; GitHub Desktop and Slack route to `ws2`.
These rules apply to newly opened windows after the desktops are labelled.
Existing windows are not automatically moved into those workspaces.

## Switch back

```sh
./wm.sh aerospace
```

This stops the trial jobs, verifies yabai/skhd have exited, opens AeroSpace,
reloads the AeroSpace SketchyBar items, and resumes the display profile switcher.
The AeroSpace configuration is preserved. Extra native desktops remain, and
the previous window positions and AeroSpace workspace assignments are not
restored from a snapshot. Use Mission Control to gather windows into your usual
desktop on each display and remove unneeded empty desktops yourself.

## Shortcuts

The baseline follows the currently active **docked** AeroSpace configuration.

| Shortcut | yabai action |
|---|---|
| Cmd + arrow | Focus neighboring window |
| Cmd + Shift + arrow | Reinsert window beside its neighbor |
| Cmd + 1–6, including keypad | Focus labelled desktop |
| Cmd + Shift + 1–6 | Send window to desktop and follow it |
| Cmd + Page Up / Page Down | Previous / next native Space |
| Cmd + Home / End | Workspace 1 / 6 |
| Alt + Tab | Previous focused Space |
| Cmd + Ctrl + left / right | Send window to previous / next display, wrapping |
| Cmd + equals / minus | Resize width |
| Cmd + Shift + equals / minus | Resize height |
| Alt + F | Fill the tiling area without native fullscreen |
| Cmd + J | Toggle the focused window's split direction |
| Cmd + comma | Toggle whole-Space BSP / stack layout |
| Cmd + Ctrl + Alt + Shift + F | Float / tile; center a newly floated window |
| Cmd + Ctrl + Alt + Shift + D | Restore BSP layout and balance windows |
| Cmd + Ctrl + Alt + Shift + R | Resize mode; arrows resize, Shift uses larger steps |
| Cmd + Ctrl + Alt + Shift + W | Workspace/display navigation mode |
| Cmd + Ctrl + Alt + Shift + M | Insertion mode; arrows choose where the next window goes |
| Cmd + Alt + S or F14 | Service mode; F floats, R balances, up/down changes volume |
| Escape / Space in a mode | Return to normal shortcuts |
| Alt + Shift + C | Reload yabai rules and skhd shortcuts |

BSP is yabai's binary split layout. Stack is not AeroSpace accordion, and
insertion is not AeroSpace container merging. Directional focus and previous/next
Space navigation stop at boundaries; only the display-send helper wraps.
Modes stay active until Escape/Space, or F15 in service mode. The old
close-all-other-windows action is not bound in this trial.

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

The existing regular and docked Lua themes select yabai items while the trial
job exists. The replacement shows desktop numbers, app icons, focused desktop,
and the active skhd mode. All six slots stay visible, with `1,3,5` on the left
and `2,4,6` on the right when using two monitors. Gray slots mean the native
desktop does not exist yet: clicking one retries automatic desktop setup.
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

The trial leaves any running JankyBorders instance alone. Initial top padding is
50 points on every display; adjust `yabairc` if the laptop notch leaves too much
space. The separate `sketchybar-light` profile is not integrated by this setup.

## Reinstall or move to another Mac

Clone this repository wherever you prefer, then run `./wm.sh install` there.
The new packages and helpers use the current home directory and support both
Homebrew prefixes. No display UUIDs, username, or checkout path is baked in.

For switching back on a fresh Mac, install AeroSpace and link the appropriate
existing AeroSpace package. To reproduce the bar, install SketchyBar and its
SbarLua dependencies and link your regular or docked SketchyBar package as usual.
The trial does not install or replace your entire desktop setup. The older
display-profile scripts still assume the repository lives at `~/dotfiles`.

Tracked files:

- `Brewfile.yabai`: optional package dependencies.
- `wm.sh`: installation, preferences, switching, rollback, and diagnostics.
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
mutually exclusive managers, label assignment, profile-switch suspension, and
SketchyBar rendering. Live Accessibility permissions, actual keyboard delivery,
hotplug, and rendering still need a manual trial after the one-time logout.

During that trial check: open/close several windows in the same app, move between
all six desktops, float/resize a window, play Nuvio video, launch apps through
Raycast, unplug/reconnect a monitor, then switch back to AeroSpace.

## Upstream references

- [yabai installation](https://github.com/asmvik/yabai/wiki/Installing-yabai-(latest-release))
- [yabai command reference](https://github.com/asmvik/yabai/blob/master/doc/yabai.asciidoc)
- [yabai SIP requirements](https://github.com/asmvik/yabai/wiki/Disabling-System-Integrity-Protection)
- [skhd configuration](https://github.com/asmvik/skhd) — the original skhd is in maintenance mode.
- [SketchyBar events](https://felixkratz.github.io/SketchyBar/config/events)
