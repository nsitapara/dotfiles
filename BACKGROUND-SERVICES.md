# Background services

Audited on 2026-09-14. macOS lists launch executables in Login Items; an entry is
not necessarily a process running continuously. Disabled app entries can remain
visible in the list.

## Desktop services to keep

| Entry | Job | When it runs |
|---|---|---|
| `switch-display-mode.sh` | `local.dotfiles.wm-login` | Once at login, with `--login yabai` or `--login aerospace`, to start the saved manager |
| `switch-display-mode.sh` | `com.user.display-mode-switcher` | Every 30 seconds, to check display profiles and retry missed changes |
| `sketchybar` | `homebrew.mxcl.sketchybar` | Continuously, to draw the menu bar |
| `borders` | `homebrew.mxcl.borders` | Continuously, to draw window borders |

The old generic `bash` startup command has been replaced with a direct call to
`switch-display-mode.sh`. The two schedules remain separate: a display check must
not start the saved manager again after a temporary switch. macOS may retain an
old entry until it refreshes its background-item inventory.

Yabai and skhd run as `local.dotfiles.yabai` and `local.dotfiles.skhd`, started by
the login command through `wm.sh`. Use `./wm.sh default status` to inspect the
saved choice. Switching and recovery commands are in [YABAI.md](YABAI.md).

## Cleanup performed

The unused `homebrew.mxcl.herdr` job was unloaded and its LaunchAgent archived in
`~/.local/state/dotfiles-wm/disabled-launch-agents/`. It referenced a missing
`/opt/homebrew/opt/herdr/bin/herdr` and had exited with code 78. No Herd package
was installed. The archived plist is available if this tool is reinstalled.

## Stale entries found, left for separate removal

| File | Finding |
|---|---|
| `~/Library/LaunchAgents/com.google.keystone.agent.plist` | Empty property list; no command configured |
| `~/Library/LaunchAgents/com.google.keystone.xpcservice.plist` | Empty property list; no command configured |
| `~/Library/LaunchAgents/org.virtualbox.vboxwebsrv.plist` | Disabled; points to a missing VirtualBox executable |
| `/Library/LaunchDaemons/SessionManagerPlugin.plist` | Contains only a label, no command; no corresponding loaded system service |

GoogleUpdater is a separate entry from the empty Keystone files. The Docker,
VPN, password-manager, and other application services are outside this cleanup.

## Script consolidation

The desktop scripts have active callers. Keep these responsibilities separate:

- `wm.sh` switches managers and handles startup failures.
- `wm-startup.py` installs or removes the saved login choice. It is not a daemon.
- `switch-display-mode.sh` is the shared startup/display entry point.
- `yabai/.config/yabai/scripts/display-profile.sh` handles native Spaces and
  SketchyBar profiles. Both display events and the periodic check invoke it.
- `aerospace-monitor-sync.sh` repairs physical display arrangements for
  AeroSpace. Its polling, retiling, and floating-window helpers remain needed
  for the supported AeroSpace fallback; they are not running while Yabai is active.
- `setup-display-switcher.sh` installs the periodic job. It only runs on demand.

A further cleanup could combine the login and periodic-job installers and replace
the hard-coded paths in `com.user.display-mode-switcher.plist` with generated
paths. Combining the runtime jobs themselves would need to preserve their
different schedules and manual-switch behavior.
