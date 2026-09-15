# Local SketchyBar window-order fix

On macOS 27.0 (build 26A428), clicking a blank area of the bar raises
SketchyBar's translucent background window above its item windows, so every
item looks dimmed. This reproduces with a minimal bar and none of the scripts in
this repository. `window-order.patch` (against SketchyBar v2.24.0, commit
`6284ee8`) keeps the bar background two window levels below items and bracket
backgrounds one level below, so a raised background can never cover them. No
polling or per-click process is involved.

## Build and approve

```sh
./scripts/build-sketchybar-window-order.sh
```

Creates `~/Applications/SketchyBar Window Order.app` with the identifier
`local.dotfiles.sketchybar-window-order`. The script refuses to overwrite an
existing app: rebuilding an ad-hoc-signed app changes its fingerprint, so remove
and re-add its permission entry after a rebuild.

Add the app under System Settings → Privacy & Security → Device Control and
Data Access (the Accessibility panel on this OS). The menu widgets need it.

## Activate

The Homebrew service plist is edited in place; save the original first.

```sh
cp ~/Library/LaunchAgents/homebrew.mxcl.sketchybar.plist \
   ~/.local/state/dotfiles-wm/sketchybar-official-service.plist
plutil -replace ProgramArguments -json \
   "[\"$HOME/Applications/SketchyBar Window Order.app/Contents/MacOS/sketchybar\"]" \
   ~/Library/LaunchAgents/homebrew.mxcl.sketchybar.plist
launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.sketchybar"
```

`brew services restart sketchybar` regenerates this plist; re-apply afterwards.
Prefer an official release once upstream fixes the ordering.

## Rollback

```sh
cp ~/.local/state/dotfiles-wm/sketchybar-official-service.plist \
   ~/Library/LaunchAgents/homebrew.mxcl.sketchybar.plist
launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.sketchybar"
```
