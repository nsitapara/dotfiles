# Mac tiling installer: research

Research for a future idempotent installer that reproduces this Mac's tiling
setup on another Mac: yabai, skhd, SketchyBar, JankyBorders and the theme.
**Status: research only, nothing built.** Recorded on October 6, 2026 against
macOS 27.0.1 (26A434), Apple Silicon, SIP enabled. File references are
relative to the repo root.

## What exists today

No single command sets up the whole stack. The shortest documented sequence
(`YABAI.md:57-122`) is:

```sh
./wm.sh install        # brew bundle Brewfile.yabai, stow yabai + skhd, build Dotfiles Spaces.app
./wm.sh prepare        # spans-displays=false, mru-spaces=false
# log out and in; grant Accessibility to yabai, skhd, Dotfiles Spaces.app
./wm.sh default yabai  # start now, and write + bootstrap the login agent
```

None of these install SketchyBar, borders, `lua@5.4`, SbarLua or the fonts, and
none starts the brew services. `setup.sh` installs AeroSpace and stows
`sketchybar` + `themes-mac`, but it doesn't touch yabai or skhd.

## Launch chain

1. `~/Library/LaunchAgents/local.dotfiles.desktop.plist` runs
   `switch-display-mode.sh --service yabai` at login. Only `wm-startup.py:95-127`
   writes it (atomic write, `launchctl enable`, `bootstrap`, or `kickstart` if
   already loaded). Reached via `./wm.sh default yabai`, `./wm.sh use yabai`
   or `./setup-display-switcher.sh --auto`.
2. `switch-display-mode.sh:14-21` runs `wm.sh yabai`, which calls
   `switch_manager` in `scripts/wm-lifecycle.sh:117-178`.
3. **Preflight (`wm-lifecycle.sh:31-49`):**
   - no legacy `com.asmvik.*`, `com.koekeishiya.*` or `homebrew.mxcl.{yabai,skhd}` jobs;
   - `yabai`, `skhd` and `jq` installed, and yabai ≥ 7.1.25;
   - `spans-displays` ≠ 1 and `mru-spaces` = 0;
   - `~/.config/{yabai,skhd}` resolve into this checkout;
   - Secure Keyboard Entry released.
4. **Daemons:** yabai and skhd run as `launchctl submit` jobs
   (`local.dotfiles.yabai`, `local.dotfiles.skhd`). No plist is written; the
   jobs disappear at logout and step 1 re-creates them at every login.
   `yabairc` touches a ready file that `start_manager` waits on.
5. **Layout (`apply_manager`):** `ensure-spaces.sh`, then
   `display-profile.sh --force`. That stows `sketchybar` or `sketchybar-docked`,
   sets per-Space padding and reloads the bar.
6. SketchyBar and borders run as plain brew services
   (`homebrew.mxcl.sketchybar`, `homebrew.mxcl.borders`); no repo script
   installs or starts them.
   - The bar picks its backend when it loads (`items/init.lua:2-13`), and
     `yabairc:116-118` reloads it if the backend isn't yabai.
   - `yabairc:23-32` restarts borders with colours from
     `~/.config/omarchy/current/borders.sh`.

## Patched builds (macOS 27)

| Build | What it does | Needed? |
|---|---|---|
| `scripts/build-yabai-fork.sh` + `yabai-fork/` | Pinned commit of our fork nsitapara/yabai (Christian-SC26 v7.1.40 plus our fixes: SIP-safe Space switching, hide-on-close windows, query JSON, and more); outputs `~/Applications/Yabai Fork.app` | **Yes on macOS 27.** Cmd+N Space switching needs it (`focus-space.py:130`); not needed on ≤ 26 |
| `scripts/use-yabai-fork.py activate` | Points `$(brew --prefix)/bin/yabai` at the fork app, saves a backup, kickstarts yabai | Needs `local.dotfiles.yabai` loaded first (`:59`) |
| `scripts/build-sketchybar-window-order.sh` + `sketchybar-patches/` | SketchyBar v2.24.0 with `window-order.patch`; outputs `~/Applications/SketchyBar Window Order.app` | Cosmetic (fixes the bar dimming on a blank click). Activation means editing the brew plist (`sketchybar-patches/README.md:27-36`) |

- **Live state:** yabai, and the running SketchyBar daemon, use the patched apps.
  The `sketchybar`, `skhd` and `borders` command-line tools are stock Homebrew.
- **Two ways Homebrew silently undoes the patches:**
  - `brew upgrade yabai` re-links the binary over the patched one;
  - `brew services restart sketchybar` regenerates its plist, dropping the
    patched binary.
- **Re-runs:** both build scripts exit 1 if their output app already exists.

### Upstream status

- **Releases:** no official yabai release supports macOS 27. The latest is
  v7.1.25 (May 8, 2026); the last commit (June 14) is a macOS 26.6 fix.
- **Open issues on asmvik/yabai:**
  - **#2822:** macOS 27 Space switching. A community fork fixes it, and
    testers in the thread confirm it works.
  - **#2828:** closing windows doesn't re-layout, with two patches:
    1. **Version check:** upstream compares the macOS major version exactly,
       so on 27 it falls back to pre-Ventura paths and never subscribes to
       window destroyed/ordered events. The fork's macOS 27 version
       predicate covers this.
    2. **Hide-on-close:** untile windows an app orders out, re-tile them on
       order-in. This is the real fix for the Spotify gap, and the fork
       carries it; see Spotify notes below.
  - **#2802, #2832:** scripting-addition offsets for macOS 27. Not needed,
    since this setup runs without the scripting addition.
- **Recheck before building:** whether stock yabai works on 27.0.1 hasn't been
  retested. The local asmvik tap clone was last updated on May 8, 2026.

## Stow packages

| Package | Target | Notes |
|---|---|---|
| `yabai`, `skhd` | `~/.config/yabai`, `~/.config/skhd` | Stowed only by `wm.sh install`; both are folded directory links |
| `sketchybar` / `sketchybar-docked` | `~/.config/sketchybar` | Mutually exclusive; `display-profile.sh:83-89` switches them, so `setup.sh` stowing `sketchybar` conflicts when docked |
| `themes-mac` | `~/.config/omarchy`, `~/CLAUDE.md` | Was `themes` before the October 5 merge |
| `bin` | `~/.local/bin/theme` | |
| `aerospace` / `aerospace-docked` | `~/.config/aerospace` | Fallback only |

**The repo has to live at `~/dotfiles`.** These committed files hard-code
`$HOME/dotfiles`:
- `skhdrc:14-21,27-28`
- `yabai/.config/yabai/scripts/window.sh:6,8`
- the SketchyBar profiles (`init.lua:19`, `items/display_profile.lua`,
  `codexbar.lua`, `amphetamine.lua`)
- `bin/.local/bin/theme:9`

`display-profile.sh:13-14` also only works because `~/.config/yabai` is a
directory link into the repo.

## Dependencies

**Homebrew:**

| Package | Status today |
|---|---|
| `asmvik/formulae/yabai`, `asmvik/formulae/skhd`, `jq`, `stow` | In `Brewfile.yabai` |
| `felixkratz/formulae/sketchybar`, `felixkratz/formulae/borders` | Not installed by any script |
| `lua@5.4` (keg-only; the `sketchybarrc:1` shebang uses it) | Not installed by any script |
| `switchaudio-osx` (`volume.lua`), `nowplaying-cli` (`media.lua`) | Not installed by any script |
| Casks `font-sf-pro`, `font-sf-mono` | Required, not installed by any script |
| Cask `font-sketchybar-app-font` | Only for CodexBar icons |
| Third-party taps (asmvik, felixkratz) | Recent Homebrew needs `brew trust` before installing from them |

**Other dependencies:**

| Dependency | Notes |
|---|---|
| SbarLua (`~/.local/share/sketchybar_lua/sketchybar.so`, `helpers/init.lua:2`) | Not installed by any script. Upstream install: `git clone FelixKratz/SbarLua && make install` |
| Xcode Command Line Tools | `swiftc` for the Spaces helper and the hover helper; `clang`/`make` for the bar helpers; `codesign` for the patched builds. Not checked: whether the patched builds work with only the Command Line Tools (Xcode.app is installed here) |
| Python | `/usr/bin/python3`, standard library only |
| Optional widget apps | CodexBar, Amphetamine (Mac App Store id 937984704) |

## macOS settings and permissions

- **Applied by `wm.sh prepare`:** `com.apple.spaces spans-displays -bool false`
  and `com.apple.dock mru-spaces -bool false`. Previous values are saved once.
  Needs a logout afterwards.
- **Set here but no script applies it:**
  - `NSGlobalDomain _HIHideMenuBar = 1`, which the hover helper needs.
  - Not referenced by the repo: Dock autohide, the
    `com.apple.WindowManager` edge-tiling keys set to 0, and
    `NSWindowShouldDragOnGesture`.
- **Accessibility** ("Device Control and Data Access" on macOS 27). These
  can't be scripted; an installer can only open the settings pane and ask for
  a re-run:
  - the yabai app or binary;
  - skhd (its Cellar path is versioned);
  - `~/Applications/Dotfiles Spaces.app`;
  - the patched SketchyBar app.
- **Automation (inferred):** probably needed for the bar's and `reveal-app.sh`'s
  System Events calls.
- **Other:** Secure Keyboard Entry must be off. No scripting addition is used.
- **Desktops:**
  - `display-layout.jq` plans 6 desktops for a laptop alone and 3 per display
    otherwise, with an error beyond one built-in screen plus two externals.
  - `Spaces.swift` creates missing desktops through Mission Control and removes
    empty unlabelled extras.

## Machine-specific bits

- **`scripts/wm/display-preferences.json`:**
  - monitor names "LG HDR QHD" and "PA278QV"; unknown names fall back to
    left-to-right order;
  - top padding 16 for the built-in screen, 50 for externals;
  - `clamshell_repair` UUIDs, used only by AeroSpace.
- **SketchyBar widgets:** `wifi.lua` assumes `en0` and the "Wi-Fi" service;
  `ssd.lua:62` assumes `disk0`.
- **`/opt/homebrew` hard-coded** in `sketchybarrc:1,5`, so Intel Macs break.
- **Theme:** `sketchybar-docked/colors.lua` is hard-coded to Catppuccin Mocha.

## Re-running existing scripts

**Already safe:**
- `wm.sh install`, except that plain `brew bundle` may upgrade yabai and
  undo the patch;
- `wm.sh prepare`;
- `display-profile.sh` with no arguments;
- `build-spaces-helper.sh` (rebuilds only if the source changed; a rebuild
  can require re-granting Accessibility);
- `wm.sh yabai` when yabai is already active;
- `wm-startup.py`.

**Side effects on re-run:**
- `wm.sh default yabai` kickstarts the login job again.
- `use-yabai-fork.py activate` restarts yabai every time.
- Both `build-*.sh` scripts exit 1 when their app already exists.
- `ensure-spaces.sh` can open Mission Control.
- Copying the SketchyBar plist again overwrites the saved original.
- `setup.sh`:
  - `stow --adopt` replaces existing real config files without a backup;
  - `verify_stow_deps` prompts when SketchyBar isn't installed yet, which
    blocks an unattended run.

## Proposed design (not built)

`./setup.sh --tiling-only`, following the `--omarchy-only` pattern; a full
`./setup.sh` on macOS would run it too. Every step checks the current state
first and skips itself if that state is already correct.

1. **Guards:**
   - macOS;
   - the repo's real path is `~/dotfiles`;
   - Command Line Tools present, otherwise `xcode-select --install` and exit
     with "re-run when done".
2. **Packages:**
   - Add the bar stack to `Brewfile.yabai`.
   - `wm.sh install` uses `brew bundle --no-upgrade` and also trusts the
     felixkratz tap.
3. **SbarLua:** install only if `sketchybar.so` is missing.
4. **Settings:**
   - `wm.sh prepare` plus `_HIHideMenuBar`, writing only values that differ.
   - If anything changed, stop with "log out, then re-run".
5. **macOS ≥ 27:** build each patched app only if its `.app` is missing.
6. **Start:**
   - Start the `sketchybar` and `borders` services only if they aren't
     loaded.
   - Run `wm.sh default yabai` only if `local.dotfiles.yabai` isn't loaded.
7. **Activate the patched builds:**
   - yabai: only if the brew link doesn't already point at the patched app.
   - SketchyBar: only if the service plist doesn't already use it; back the
     plist up only when no backup exists.
8. **Permissions:** if `yabai -m query --spaces` fails after starting, open
   the Accessibility pane, list the grants and exit asking for a re-run.
9. **Fixes:**
   - The `theme` path (see Known bugs).
   - Stop stowing `sketchybar` from `setup.sh` on macOS, since
     `display-profile.sh` owns that choice.

**Testing:**
- `bash -n`, plus `shellcheck` if available;
- run `--tiling-only` twice on an already set-up Mac: it must restart no
  daemon (same PIDs), leave no git diff and ask no questions;
- the fresh-install path can only be tested on the new Mac.

**Left out:** Dock autohide, Raycast, the CodexBar and Amphetamine apps.

## Known bugs found during research

- **`theme switch` is broken.** `bin/.local/bin/theme:9` still points at
  `$HOME/dotfiles/themes/...`, but the October 5 merge renamed the package
  to `themes-mac`.

## Spotify notes

- **Floated on purpose:** `yabairc` sets `manage=off` for Spotify. Its close
  button only orders the window out, and the reopened window gets a new AX
  element under the same window id. yabai ignores that element for a known id
  (upstream `src/event_loop.c:556`), so it can never move the window again.
- **Reopen on switch:** `reveal-app.sh` sends a reopen when every known window
  of the app it's switching to is ordered out, so Cmd+Tab brings Spotify's
  window back.
- **Cleanup later:** the fork now carries the #2828 hide-on-close and
  reopened-window fixes. Re-test Spotify as a tiled window (close, then
  reopen) and consider dropping both workarounds.
