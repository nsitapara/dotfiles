# Native menu hover

Both Lua SketchyBar profiles start `run.py`. It builds the Swift helper in
`~/.cache/dotfiles/sketchybar-hover` and replaces its previous instance on reload.
The helper exits when the SketchyBar daemon stops. It polls the pointer at 30 Hz
without requiring Accessibility or Input Monitoring permission.

Move the pointer into the top two points of a display to slide SketchyBar down
36 points, or the notch safe-area height if larger. It returns after the pointer
has left the native menu and moved bar for 350 ms. Dragging does not trigger it.
The temporary second row overlaps the top of app windows; it does not retile
windows. SketchyBar's offset is global, so all displays move together.

The helper uses `topmost=window` so native dropdown menus stay above it. Stopping
it restores `topmost=off y_offset=0`:

```sh
python3 ~/dotfiles/sketchybar-hover/run.py stop
```

It starts again on the next SketchyBar reload. Remove the `run.py` invocation
from both profiles' `init.lua` files to disable it permanently.

Check the state transitions without moving the real pointer:

```sh
swiftc sketchybar-hover/HoverState.swift tests/test_sketchybar_hover.swift -o /tmp/test-sketchybar-hover
/tmp/test-sketchybar-hover
```

Related upstream reports:

- [SketchyBar #810](https://github.com/FelixKratz/SketchyBar/pull/810): merged macOS 26 menu-height correction.
- [SketchyBar #833](https://github.com/FelixKratz/SketchyBar/pull/833): proposed fix for zero menu insets on external displays.
- [sketchybar-toggle](https://github.com/malpern/sketchybar-toggle): alternative that hides the bar on hover.
