# Display modes: docked, laptop, and Screen Sharing

Three layouts have to work. They are pinned from the bar's profile menu (the pill on the right, or `./wm.sh profile NAME`); the Auto entry detects once from the connected screens. Nothing polls displays. A pin the connected screens cannot satisfy falls back to Auto and shows greyed in the bar:

| Layout | Displays | Profile stowed |
|---|---|---|
| Docked (clamshell) | LG HDR QHD + PA278QV | `aerospace-docked` + `sketchybar-docked` |
| Laptop alone | built-in only | `aerospace` + `sketchybar` |
| Screen Sharing session | 1 virtual display, externals released | `aerospace` + `sketchybar` |

The remote case reuses the laptop profile on purpose: macOS hands the session a
single virtual display and detaches the physical ones, so "one display, no
per-monitor split" is exactly right. No third profile exists.

## What switches them

| Piece | Role |
|---|---|
| `switch-display-mode.sh` | Counts displays, unstows/stows the matching profile, reloads AeroSpace + sketchybar. Idempotent — exits early when the mode and the stowed config already agree. |
| `local.dotfiles.desktop` (launchd) | Starts the saved manager once at login, which applies the pinned profile once. The single service is installed by `./wm.sh default yabai` or `aerospace`. |
| `aerospace-monitor-sync.sh` | Runs it *immediately*, off sketchybar's built-in `display_change` event, and repairs the arrangement first. |

The switcher waits for two matching display snapshots before applying a profile.
It tracks the display count and SketchyBar display identities/geometry, excluding
human-readable profiler diagnostics such as refresh-rate text. Changing a monitor
without changing the number of screens still refreshes the assignments. A layout
refresh reloads only SketchyBar; it does not restow unchanged files or reload
AeroSpace. Missing cached state alone does not reset a matching live profile.
Checks made while the bar is stopped preserve the last running layout, and an
unavailable profile marker defers action until a later check. Each applied change
logs its timestamp and reason.
Failed or zero-display detection leaves the existing profile alone for the next
event or 30-second check to retry.

Both scripts use macOS `lockf` to prevent overlapping runs. Display events no
longer kill a pending switch while it is changing symlinks. The event handler
writes directly to the switcher logs so reloading its parent Lua config cannot
close its output pipe halfway through the switch.

SketchyBar must be reloaded with an explicit config path:
`sketchybar --reload "$HOME/.config/sketchybar/sketchybarrc"`. A bare `--reload`
reuses the previously resolved path, which can leave the docked profile running
after Stow has selected the laptop profile. That caused only 1, 3, and 5 to show
on the laptop while 2, 4, and 6 remained assigned to the disconnected monitor.
Each Lua config now adds a hidden `display_mode` item after loading its items.
The switcher verifies that item before recording success, and checks it on later
runs to recover if the running profile and symlinks disagree.

Mode and display snapshots are stored in `${TMPDIR:-/tmp}/.display-mode-state`
and its `.displays` companion. Run the isolated regression tests on macOS with
`python3 tests/test_display_mode_switcher.py`. They simulate repeated docking,
unplugging, config desynchronization, failed detection/reloads, and concurrent
invocations without changing the live desktop.

Without the event hook the wrong AeroSpace profile stays stowed until a profile is
re-pinned: workspaces force-assigned to a monitor that isn't there, space pills
pinned to a dead display index. That is what made sketchybar look "cut off" after
connecting a Screen Sharing session. Under yabai, display changes only refresh
the pills; the profile changes when you pick one.

## Trap: three different display numbers

`sketchybar-docked/.config/sketchybar/items/spaces.lua` pins each workspace pill
to the monitor its windows live on. Doing that means crossing between numbering
schemes that are **not interchangeable**, and mistaking one for another silently
puts every pill on the wrong bar:

| Number | Whose | Ordering |
|---|---|---|
| monitor index | AeroSpace (`list-monitors`) | its own left-to-right sweep by x |
| `monitor-appkit-nsscreen-screens-id` | AeroSpace | NSScreen enumeration position — **not stable across reboots** |
| `DirectDisplayID` | sketchybar (`--query displays`) | CoreGraphics id — **re-assigned across reboots** |
| `arrangement-id` | sketchybar | System Settings → Displays arrangement order. **This is what the `display` property takes.** |

An earlier version of `spaces.lua` joined AeroSpace → sketchybar on
`monitor-appkit-nsscreen-screens-id == DirectDisplayID`. That equality was a
coincidence of one boot's enumeration, not an invariant: after a restart
AeroSpace reported nsscreen ids {1, 2} while sketchybar reported
DirectDisplayIDs {2, 3}, the join produced garbage, and every pill landed on
one bar.

`spaces.lua` now joins on **monitor name** (`%{monitor-name}`), the only
identifier that survives reboots, with a static name → arrangement-id map
(`LG HDR QHD` → 1, `PA278QV` → 2). The map can be static because
`aerospace-monitor-sync.sh` enforces the golden arrangement below — LG at
`(0,0)` is arrangement 1, PA278QV to its right is arrangement 2.

Do not "simplify" that to the AeroSpace monitor index either. It only appears
to work when the arrangement happens to be strictly left-to-right with the
leftmost display also being arrangement 1.

## Trap: macOS scrambles the arrangement after Screen Sharing

A session releases the physical displays and re-attaches them on disconnect —
scrambled. Observed after one session:

```
built-in   (0,0)        enabled, and Main Display, with AppleClamshellState = Yes
LG         (-494,-1440) stacked above instead of beside
PA278QV    (1728,0)
```

Two separate faults. The built-in re-enumerates as an active display **even with
the lid shut** — a macOS clamshell bug, not a config problem; `ioreg -k
AppleClamshellState` correctly reports the lid closed the whole time. And the
externals come back stacked, leaving them sharing only a 338pt corner, so the
mouse can barely cross between them and every monitor-relative AeroSpace command
has to hop through a screen nobody can see.

`aerospace-monitor-sync.sh` restores a golden arrangement via `displayplacer`
(LG left at `(0,0)`, PA278QV right at `(2560,0)`, built-in disabled). Guards:

- Only when the lid is closed **and** both externals are present by UUID. Laptop
  alone, a Screen Sharing virtual display, and a genuinely open lid are all
  legitimate layouts and are left alone.
- Only when the current arrangement differs from golden. Applying an arrangement
  emits another `display_change`, so without this check it would loop forever. A
  *disabled* built-in counts as correct alongside an absent one — otherwise the
  check could never be satisfied.

Re-snapshot the golden values with `displayplacer list | tail -1` if the desk
setup changes. The UUIDs are hardcoded, so docking elsewhere makes the repair
inert rather than wrong.

Note macOS resists the broken geometry once the built-in is genuinely off — it
snaps two displays back to side-by-side. The corner-touching layout was only
reachable *because* the phantom built-in bridged them.

## Gotchas

- `outer.top` is per-monitor in **both** profiles. The built-in needs only 16
  because the notch makes the native menu bar taller; anything else needs 50 to
  clear the 40pt sketchybar. The virtual display is 1440x900 logical and has no
  notch, so a flat 16 puts windows *under* the bar.
- `[workspace-to-monitor-force-assignment]` pins by monitor **name** with
  `main`/`secondary` as fallback. Bare `secondary` means "any non-main monitor",
  so a third display — Screen Sharing's virtual one — matches it and steals
  workspaces 4-6 onto a screen that isn't there.
- Force assignment **vetoes** `move-workspace-to-monitor`: it fails with
  *"workspace-to-monitor-force-assignment doesn't allow it"*, which makes
  `cmd-ctrl-left`/`cmd-ctrl-right` dead while docked. `move-node-to-monitor`
  (per-window) is unaffected and works. An *unmatched* pattern imposes no
  constraint at all, so workspaces go free when their monitor is absent.
- If the built-in stays dark after opening the lid, re-enable it with
  `displayplacer "id:37D8832A-2D66-02CA-B9F7-8F30A301B230 enabled:true"`.

## Not yet verified

The disconnect-repair path has never fired for real. Reproducing it requires an
actual Screen Sharing session to scramble the arrangement — it cannot be
simulated, because macOS refuses the broken geometry with only two displays
attached. The `displayplacer` command itself is proven (it is what fixed the
monitors originally, built-in disable included) and the no-op guard is tested;
only the automatic trigger on that exact sequence is untested. If a disconnect
leaves things wrong, check `/tmp/display-mode-switcher.log` and
`displayplacer list | tail -1`.
