# Native menu hover

Both Lua SketchyBar profiles start `run.py`. It builds the Swift helper in
`~/.cache/dotfiles/sketchybar-hover` and replaces its previous instance on reload.
The helper exits when the SketchyBar daemon stops. It polls the pointer at 10–30 Hz
without requiring Accessibility or Input Monitoring permission.
The builder resolves Swift and its SDK through Xcode's `xcrun`, clears inherited
SDK/deployment overrides, and targets macOS 13 or later. This avoids mixing the
older Xcode compiler with SDK settings inherited during the OS upgrade.

SketchyBar hands off to the native menu bar only after the pointer has stayed
in the top zone for 3 seconds (`HoverState.revealDelay`) and macOS has revealed
its auto-hidden menu bar; brushing the top edge alone does nothing. While the delay runs the helper keeps the native bar
transparent with the private `SLSSetMenuBarInsetAndAlpha` call (the SketchyBar
menus helper uses the same call), and keeps it transparent while it slides away
if the pointer leaves early. A menu opened from the keyboard (pointer away from
the top for over a second) hands off at once. The helper restores full opacity
when it starts and when it stops; if it is force-killed mid-delay and the native
bar stays invisible, reload SketchyBar.
An open SketchyBar popup pauses that handoff and resets its timer. This prevents
the first menu click from opening a popup just as the helper hides the entire bar
(and closes the popup). The existing window-metadata scan recognizes popup-level
windows owned by this SketchyBar process, including a custom app bundle name.
Parked off-screen popup windows do not count. The scan continues at 10 Hz while
a popup is open, with no extra process or polling timer.

It stays hidden while the native menu bar is visible,
including when the pointer moves down into an open dropdown. It returns after
the native menu closes and the pointer has left its top zone for 350 ms.

The helper checks on-screen window metadata to detect the native menu bar,
without capturing screen contents: 1 Hz while the bar is shown and the pointer
is away from the top, 10 Hz while hidden, and every tick while the pointer is in
the menu zone. Screen geometry is cached and refreshed once a second. macOS 27
marks some window layers with bit 31; this flag is masked when identifying the
menu layer. The pointer is polled at 30 Hz within 200 pt of the top or during a
hand-off, and at 10 Hz otherwise. `run.py` links the helper against the private
SkyLight framework. The native menu must be configured to auto-hide.

SketchyBar remains at `y_offset=0`; there is no second row or window retiling.
Visibility is global, so all displays hide/show together.

The helper uses `topmost=on` to keep SketchyBar items above the native menu's
click area. At `topmost=window`, the first click after using another app could
select that area instead; a live test confirmed the higher level fixes it.
Native dropdowns remain above the bar, and the hover handoff still hides it.
Stopping it restores `topmost=off hidden=off y_offset=0`:

```sh
python3 ~/dotfiles/sketchybar-hover/run.py stop
```

It starts again on the next SketchyBar reload. Remove the `run.py` invocation
from both profiles' `init.lua` files to disable it permanently.
If the helper is force-killed while the bar is hidden, restore it with
`sketchybar --bar hidden=off y_offset=0` or reload SketchyBar.

Check the state transitions without moving the real pointer:

```sh
swiftc sketchybar-hover/HoverState.swift tests/test_sketchybar_hover.swift -o /tmp/test-sketchybar-hover
/tmp/test-sketchybar-hover
```

Live validation on macOS 27 confirmed `hidden=on y_offset=0` while a CodexBar
native menu was open, then `hidden=off y_offset=0` after dismissing it.

Related upstream reports:

- [SketchyBar #810](https://github.com/FelixKratz/SketchyBar/pull/810): merged macOS 26 menu-height correction.
- [SketchyBar #833](https://github.com/FelixKratz/SketchyBar/pull/833): proposed fix for zero menu insets on external displays.
- [sketchybar-toggle](https://github.com/malpern/sketchybar-toggle): related hide/show implementation.

The launcher follows the oldest matching SketchyBar process, including ancestors.
Short-lived IPC clients share the daemon's process name and can have lower PIDs
after PID wrap; following one makes the helper exit as soon as that client ends.
The launcher regression runs with `python3 -m unittest discover -s tests -p test_sketchybar_hover_launcher.py`.
