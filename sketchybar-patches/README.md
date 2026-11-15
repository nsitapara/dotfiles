# Local SketchyBar window-order and unlock fixes

On macOS 27.0 (build 26A428), clicking a blank area of the bar raises
SketchyBar's translucent background window above its item windows, so every
item looks dimmed. This reproduces with a minimal bar and none of the scripts in
this repository. `window-order.patch` (against SketchyBar v2.24.0, commit
`6284ee8`) keeps the bar background two window levels below items and bracket
backgrounds one level below, so a raised background can never cover them. No
polling or per-click process is involved.

## Unlock without recreating every window

`unlock-refresh.patch` separates `com.apple.screenIsUnlocked` from actual system
wake. Upstream v2.24.0 routes both to `SYSTEM_WOKE`, which destroys and recreates
every bar and item window. A live lock/unlock trace reproduced the blank flash
without any hide/show command from our hover helper or any daemon restart.

Unlock now refreshes Space/display state, redraws existing items, restores their
ordering, and still sends `system_woke` to widgets. Actual sleep/wake keeps the
upstream rendering recovery path. This targets the flash on unlock; it does not
promise to remove the OS transition or renderer recovery after real sleep.

The build runs `tests/test_sketchybar_unlock.py` against the patched native
handlers. The same test fails against the original handler because it rebuilds
the windows. A complete arm64 native build also verifies the event/observer wiring.

For an existing installation, build to a new path so the old signed app remains
available for rollback:

```sh
./scripts/build-sketchybar-window-order.sh "$HOME/Applications/SketchyBar Unlock Fix.app"
```

Activate that new executable through the launch-agent `ProgramArguments` below,
using the new app path. Preserve the current plist first. The new ad-hoc-signed
build may need its Accessibility permission reauthorized; do not overwrite the
already authorized app in place.

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
