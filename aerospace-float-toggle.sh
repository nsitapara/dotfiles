#!/bin/bash
# Float/tile toggle for the focused window. When a window BECOMES floating,
# resize it to 95% of ITS screen (minus sketchybar clearance) and center it
# there, so it visibly pops out of the layout. AeroSpace has no float-size
# memory or positioning commands, and `aerospace resize` doesn't support
# floating windows (upstream issue #9), so both go through the AX API via JXA.
#
# Gotchas encoded here:
# - AXFocusedWindow, NOT windows[0]: with two windows of the same app on two
#   screens, windows[0] can be the wrong one (float jumped to the other monitor)
# - screen chosen by containment of the window's center, NOT NSScreen.mainScreen
# - position set before size, then re-set: setting size first makes macOS
#   constrain against the old position (visible double-jump)
# - top inset mirrors the aerospace outer.top gap (16 built-in / 50 external)
#   because sketchybar doesn't reserve space in NSScreen.visibleFrame
AS=/opt/homebrew/bin/aerospace
if "$AS" layout floating --fail-if-noop 2>/dev/null; then
    /usr/bin/osascript -l JavaScript >/dev/null 2>&1 <<'EOF'
ObjC.import('Cocoa')
const proc = Application('System Events').processes.whose({ frontmost: true })[0]
const win = proc.attributes.byName('AXFocusedWindow').value()
const pos = win.position(), size = win.size()
const primaryH = $.NSScreen.screens.js[0].frame.size.height
// window center in Cocoa (bottom-left) coords
const cx = pos[0] + size[0] / 2
const cy = primaryH - (pos[1] + size[1] / 2)
const screens = $.NSScreen.screens.js
const screen = screens.find(s => {
    const f = s.frame
    return cx >= f.origin.x && cx < f.origin.x + f.size.width &&
           cy >= f.origin.y && cy < f.origin.y + f.size.height
}) || $.NSScreen.mainScreen
const vf = screen.visibleFrame
const topInset = /built-in/i.test(screen.localizedName.js) ? 16 : 50
const uh = vf.size.height - topInset
const w = Math.round(vf.size.width * 0.95)
const h = Math.round(uh * 0.95)
const x = Math.round(vf.origin.x + (vf.size.width - w) / 2)
const seTop = primaryH - (vf.origin.y + vf.size.height)
const y = Math.round(seTop + topInset + (uh - h) / 2)
win.position = [x, y]
win.size = [w, h]
win.position = [x, y]
EOF
else
    "$AS" layout tiling
fi
