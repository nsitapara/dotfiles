# Background services

Audited on 2026-09-14. macOS lists launch executables in Login Items; an entry is
not necessarily a process running continuously. Disabled app entries can remain
visible in the list.

## Desktop services to keep

| Entry | Job | When it runs |
|---|---|---|
| `switch-display-mode.sh` | `local.dotfiles.desktop` | Starts the saved manager once at login, then checks display profiles every 30 seconds |
| `sketchybar` | `homebrew.mxcl.sketchybar` | Continuously, to draw the menu bar |
| `borders` | `homebrew.mxcl.borders` | Continuously, to draw window borders |

There is one desktop startup/checking job. The old `local.dotfiles.wm-login` and
`com.user.display-mode-switcher` jobs are unloaded and their plists archived under
`~/.local/state/dotfiles-wm/disabled-launch-agents/`. The service starts the manager
once, then only checks displays. A temporary manager switch stays in effect.
macOS may retain old entries until it refreshes its background-item inventory.

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
- `setup-display-switcher.sh --auto` calls the same installer as `wm.sh default`.
  It cannot install a separate polling job.

The old hard-coded plist template has been removed. `wm-startup.py` generates the
single service's paths from the current checkout. Reinstalling preserves the
saved manager, and `./wm.sh default off` removes the service without stopping the
current manager or its event-driven display handlers.
