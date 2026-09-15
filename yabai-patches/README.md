# Local macOS 27 yabai build

The installed OS reports macOS 27.0, build 26A428. Stock yabai 7.1.25 accepts
`space --focus` but does not switch desktops with SIP enabled on this build.
This local patch restores the Dock gesture payload and keeps window management
on yabai's modern macOS paths. It does not install a scripting addition or
change SIP.

## Sources

- yabai base: `dd845723416f5fe92af49fad5ebab00369e07edd`, version 7.1.25.
- [yabai #2822](https://github.com/asmvik/yabai/issues/2822) documents the
  SIP-enabled desktop-switching regression.
- [InstantSpaceSwitcher 79a17c4](https://github.com/geesawra/InstantSpaceSwitcher/commit/79a17c4dd041639751a3d6087009864a2d6dcf1b)
  supplies the IOHID event serializer. Its MIT license is included in the patch.
- [yabai #2800](https://github.com/asmvik/yabai/issues/2800) describes using the
  macOS 26 main-binary paths on macOS 27. This patch limits that alias to 27.

The local integration sends Began, Changed, and Ended phases, with velocity only
on Ended. It constructs all three before posting. Positive progress/velocity
select the next desktop on the tested 26A428 build; the inverted signs in the
linked ISS fork moved to the previous desktop here. Existing gesture behavior
on older macOS versions stays intact. yabai already uses
`SLSManagedDisplayGetCurrentSpace`, so no active-Space lookup change was needed.

## Build and approve

```sh
./scripts/build-yabai-macos27.sh
```

This fetches the pinned yabai revision into a temporary directory, applies the
patch, builds both architectures, runs payload tests with UndefinedBehaviorSanitizer,
and creates `~/Applications/Yabai macOS 27.app`. The script refuses to overwrite
an existing output. Pass a different output path to inspect a rebuild.

Add **Yabai macOS 27.app** under System Settings → Privacy & Security → Device
Control and Data Access, then enable it. This is the Accessibility permission
panel's name on the tested OS. The app has the separate identifier
`local.dotfiles.yabai-macos27`, which distinguishes it from the original yabai
entries. Rebuilding an ad-hoc-signed app changes its fingerprint and can require
removing and re-adding its permission entry.

```sh
python3 scripts/use-yabai-macos27.py activate
```

Activation requires the normal dotfiles yabai service to be loaded. It saves the
existing Homebrew symlink, points it at the approved app, and restarts the service.
The original Cellar binary is preserved. Existing startup scripts and shortcuts
continue using the normal `yabai` command. A Homebrew upgrade can replace this
symlink; prefer an official fixed release when one becomes available.

## Rollback

```sh
python3 scripts/use-yabai-macos27.py rollback
```

The saved link is in `~/.local/state/dotfiles-wm/yabai-macos27-backup.json`.
Rollback refuses to overwrite a link already changed by another tool.

## Replace this with an official release

Do this when the [official yabai releases](https://github.com/asmvik/yabai/releases)
include the macOS 27 fixes. A newer version number alone is insufficient: check
that **SIP-enabled** Space switching is fixed, along with the main-binary OS
version checks. A release that only fixes the scripting addition does not solve
this setup's problem. Track the linked issues above for that distinction.

1. Keep `Yabai macOS 27.app` until the official version passes the live checks.
2. Restore the Homebrew link, upgrade through the official tap, and restart the
   existing dotfiles service:

   ```sh
   python3 scripts/use-yabai-macos27.py rollback
   brew update
   brew upgrade asmvik/formulae/yabai
   launchctl kickstart -k "gui/$(id -u)/local.dotfiles.yabai"
   ```

   If Homebrew already replaced the custom link, the rollback command stops
   without changing it. Inspect the resolved path and proceed with the upgrade.
   If no fixed package is available yet, reactivate the workaround.

3. Confirm the command resolves into Homebrew's Cellar, not the local app:

   ```sh
   python3 -c 'import pathlib, shutil; print(pathlib.Path(shutil.which("yabai")).resolve())'
   yabai --version
   ```

   On this Mac the expected official path is
   `/opt/homebrew/Cellar/yabai/<version>/bin/yabai`. Grant the official binary
   Device Control and Data Access if macOS requests it. Keep using the existing
   `local.dotfiles.yabai` service; do not start a second Homebrew service.

4. Verify the actual desktop changes, not just the command's exit code:
   - Switch to the next desktop and back with Cmd+number.
   - Jump across at least two desktops, then return.
   - Move a window to another desktop and follow it, then restore it.
   - Check directional focus, window swaps/resizing, and automatic tiling.
   - Log out and back in once to confirm the official binary starts at login.

5. If a check fails, run `python3 scripts/use-yabai-macos27.py activate` to
   restore the approved local app. Investigate before removing it.
6. Once the official build passes, remove the workaround in a focused commit:
   - Delete `yabai-patches/`, `scripts/build-yabai-macos27.sh`,
     `scripts/use-yabai-macos27.py`, and `tests/test_yabai_gesture.c`.
   - Remove the temporary-build section from `YABAI.md`.
   - Remove `~/Applications/Yabai macOS 27.app` and its permission entry.
   - Remove the saved `yabai-macos27-backup.json` and the build caches under
     `~/.cache/dotfiles/yabai-macos27/`. The earlier trial executable under
     `~/.local/opt/yabai-macos27/` can also be removed.

Keep `yabairc`, skhd, the startup/display watcher, Dotfiles Spaces, the border
theme setup, and the SketchyBar hover/menu-item fixes. They are separate from
this yabai workaround and are not removed during the official-release migration.

## Installation record, September 14, 2026

| Item | Value |
|---|---|
| OS | macOS 27.0, build 26A428 |
| Local app | `~/Applications/Yabai macOS 27.app` |
| App identifier | `local.dotfiles.yabai-macos27` |
| Command link | `/opt/homebrew/bin/yabai` → local app's `Contents/MacOS/yabai` |
| Original binary | `/opt/homebrew/Cellar/yabai/7.1.25/bin/yabai` |
| Service | `gui/501/local.dotfiles.yabai` |
| SIP | Enabled; no scripting addition installed by this change |

The initially installed app is the ARM64 test build. The checked-in build
script produces a universal binary from the same patch. Both recipes compiled
successfully; the live desktop tests used the installed ARM64 build.

## Verification on this Mac

- Fresh pinned build and code-signature verification passed.
- Serialized payload tests passed for both directions and all three phases.
- Desktop sequences 2 → 3 → 2 → 4 → 2 and 6 → 5 → 4 → 6 passed.
- The background service passed the same desktop-switching checks after app approval.
- An injected Cmd+5 shortcut selected desktop 5; the test restored the original desktop.

AddressSanitizer from the installed Xcode hung during runtime initialization on
this OS, before the test's `main`. The checked-in test uses UndefinedBehaviorSanitizer.
This remains a local compatibility patch, not an official yabai macOS 27 release.
