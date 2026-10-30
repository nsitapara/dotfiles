# yabai fork build (macOS 27)

This Mac runs yabai from our fork, [nsitapara/yabai](https://github.com/nsitapara/yabai)
(`master`, which equals `macos27-combined`). The fork is Christian-SC26/yabai plus our
fixes: SIP-on space switching that never drops a press, hide-on-close and reopened
windows, a click during a retile, busy apps' windows, wake-time display hardening,
and Mission Control focus restore. See `FORK.md` in the fork for each commit, how to
build it and the live checklist. The patches that used to live here are now commits
in the fork. The checks that test them run as `tests/local/run.sh` there.

| Item | Value |
|---|---|
| App | `~/Applications/Yabai Fork.app` (`local.dotfiles.yabai-fork`) |
| Source | `scripts/build-yabai-fork.sh` pins the fork commit |
| Command link | `/opt/homebrew/bin/yabai` → the app's `Contents/MacOS/yabai` |
| Backup of the previous link | `~/.local/state/dotfiles-wm/yabai-fork-backup.json` |
| Service | `gui/<uid>/local.dotfiles.yabai`; SIP enabled, no scripting addition |

## Build, approve, activate

```sh
./scripts/build-yabai-fork.sh [output.app]
```

The script fetches the pinned fork commit, runs the fork's event-free checks, builds with
a serial `make install`, and signs an ad-hoc app bundle. It refuses to overwrite an existing
app, so pass another path to inspect a rebuild. A rebuild changes the app's fingerprint, so
remove and add the app again under System Settings → Privacy & Security → Device Control and
Data Access.

```sh
python3 scripts/use-yabai-fork.py activate    # point the yabai command at the app, restart
python3 scripts/use-yabai-fork.py rollback    # restore the saved link
```

The rollback target is `~/Applications/Yabai macOS 27.app`, the earlier patched 7.1.25 build.
Keep that app and its permission until the fork has run for a while.

## Updating

Merge a new Christian-SC26 release into `macos27-combined` in `~/Documents/GitHub/yabai`,
run `tests/local/run.sh` and `make -C tests build` there (never run the fork's test binary
on this Mac: it posts real gestures and clicks), push, fast-forward `master`, then bump
`revision` in `scripts/build-yabai-fork.sh` and rebuild to a new path.

## Known behaviour

- A space switch made within about half a second of cancelling Mission Control is reverted
  to the space Mission Control was opened from. This comes from the fork's Mission Control
  restore logic (both v7.1.39 and v7.1.40). Wait briefly after Esc.
- `yabai --version` prints the fork's version (7.1.40). Check the binary's path to tell builds apart.
