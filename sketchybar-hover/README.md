# Native menu hover

Both Lua SketchyBar profiles start `run.py`. It builds the Swift helper in
`~/.cache/dotfiles/sketchybar-hover` and replaces its previous instance on reload.
The helper exits when the SketchyBar daemon stops. It polls the pointer at 30 Hz
without requiring Accessibility or Input Monitoring permission.
The builder resolves Swift and its SDK through Xcode's `xcrun`, clears inherited
SDK/deployment overrides, and targets macOS 13 or later. This avoids mixing the
older Xcode compiler with SDK settings inherited during the OS upgrade.

Move the pointer into the top two points of a display to hide SketchyBar while
the native menu appears. It stays hidden while the native menu bar is visible,
including when the pointer moves down into an open dropdown. It returns after
the native menu closes and the pointer has left its top zone for 350 ms.
Dragging to the top does not trigger hiding by itself.

The helper checks on-screen window metadata at 10 Hz to detect the native menu
bar, without capturing screen contents. macOS 27 marks some window layers with
bit 31; this flag is masked when identifying the menu layer. Pointer polling
remains 30 Hz. The native menu must be configured to auto-hide.

SketchyBar remains at `y_offset=0`; there is no second row or window retiling.
Visibility is global, so all displays hide/show together.

The helper uses `topmost=window` so native dropdown menus stay above it. Stopping
it restores `topmost=off hidden=off y_offset=0`:

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
