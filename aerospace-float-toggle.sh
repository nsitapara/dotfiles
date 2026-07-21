#!/bin/bash
# Float/tile toggle for the focused window. When a window BECOMES floating,
# shrink it to 1600x1000 so it visibly pops out of the layout (AeroSpace has
# no float-size memory, and `aerospace resize` doesn't support floating
# windows — upstream issue #9 — so the shrink goes through the AX API).
AS=/opt/homebrew/bin/aerospace
if "$AS" layout floating --fail-if-noop 2>/dev/null; then
    /usr/bin/osascript -e 'tell application "System Events" to tell (first process whose frontmost is true) to set size of front window to {1600, 1000}' >/dev/null 2>&1
else
    "$AS" layout tiling
fi
