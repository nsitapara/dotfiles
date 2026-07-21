#!/bin/bash
# Float/tile toggle for the focused window. When a window BECOMES floating,
# shrink it (target 1600x1000, clamped to 90% of the screen) and center it on
# its screen so it visibly pops out of the layout. AeroSpace has no float-size
# memory or positioning commands, and `aerospace resize` doesn't support
# floating windows (upstream issue #9), so both go through the AX API via JXA
# (NSScreen.mainScreen = screen with keyboard focus).
AS=/opt/homebrew/bin/aerospace
if "$AS" layout floating --fail-if-noop 2>/dev/null; then
    /usr/bin/osascript -l JavaScript >/dev/null 2>&1 <<'EOF'
ObjC.import('Cocoa')
const vf = $.NSScreen.mainScreen.visibleFrame
const w = Math.min(1600, Math.round(vf.size.width * 0.9))
const h = Math.min(1000, Math.round(vf.size.height * 0.9))
const x = Math.round(vf.origin.x + (vf.size.width - w) / 2)
// System Events uses top-left global coords; NSScreen uses bottom-left
const primaryH = $.NSScreen.screens.js[0].frame.size.height
const cocoaY = vf.origin.y + (vf.size.height - h) / 2
const y = Math.round(primaryH - (cocoaY + h))
const win = Application('System Events').processes.whose({ frontmost: true })[0].windows[0]
win.size = [w, h]
win.position = [x, y]
EOF
else
    "$AS" layout tiling
fi
