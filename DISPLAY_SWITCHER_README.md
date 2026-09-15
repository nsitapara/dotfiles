# Automatic display switching

One desktop service starts the saved window manager at login, which applies the
pinned display profile once. Pick a profile from the bar menu or `./wm.sh profile`;
nothing polls displays. Yabai
and AeroSpace share the monitor policy; see [DISPLAY-MODES.md](DISPLAY-MODES.md)
for display behavior and [YABAI.md](YABAI.md) for installation and recovery.

## Commands

Run from this checkout:

```sh
./wm.sh default yabai       # Use Yabai now and at login; enable display checks
./wm.sh default aerospace   # Switch to AeroSpace now and at login
./wm.sh default status      # Show the saved manager
./wm.sh default install     # Repair/reinstall, preserving the saved manager
./wm.sh default off         # Remove the service; leave the current manager running
./wm.sh profile docked      # Pin a profile: auto, docked, single, laptop
./wm.sh profile             # Show the pinned and applied profile
./switch-display-mode.sh    # Apply the pinned profile once without switching managers
```

For compatibility, `./setup-display-switcher.sh --auto` invokes the same installer.
With no saved choice it selects Yabai. Without `--auto`, that setup script checks
dependencies and builds the Spaces helper without installing a background job.

## Service behavior

The only startup/checking LaunchAgent is
`~/Library/LaunchAgents/local.dotfiles.desktop.plist`. It directly runs
`switch-display-mode.sh --service yabai` or `--service aerospace`.

The service starts the selected manager once, then sleeps between display checks.
It does not restart a manager during periodic checks, so `./wm.sh aerospace` and
`./wm.sh yabai` remain temporary switches until the next login. A failed display
check is retried on the next interval. A failed initial manager startup exits and
is recorded in the logs.

The installer removes and archives the previous `local.dotfiles.wm-login` and
`com.user.display-mode-switcher` jobs. The static plist template has been retired;
paths are generated from the current checkout. After moving the checkout, rerun
`./wm.sh default install` there.

## Diagnostics

```sh
./wm.sh doctor
launchctl print "gui/$(id -u)/local.dotfiles.desktop"
tail -n 50 ~/.local/state/dotfiles-wm/login.err.log
```

The service writes to `login.log` and `login.err.log` in
`~/.local/state/dotfiles-wm/`. AeroSpace's immediate display event handler also
writes `/tmp/display-mode-switcher.log` and `/tmp/display-mode-switcher.err`.
Disabled legacy plists are backed up under
`~/.local/state/dotfiles-wm/disabled-launch-agents/`.

If configuration changes are not applied, run `./switch-display-mode.sh` once
and inspect its output. If the service has exited, use `./wm.sh default install`
to restart it with the saved choice. Do not install an additional polling agent.

## Validation

```sh
python3 -m unittest discover -s tests -p 'test_wm*.py'
python3 -m unittest discover -s tests -p test_display_mode_switcher.py
```

Tests cover migration to one job, startup failure, repeated installation,
manual manager switches, failed display checks, and display-profile changes
without touching the live desktop.
