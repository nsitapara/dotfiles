# AeroSpace re-tile workaround (TEMPORARY)

AeroSpace 0.20/0.21 moved window detection to per-app background threads, so
new/closed windows re-tile late (or not until nudged). Upstream bug:
<https://github.com/nikitabobko/AeroSpace/issues/1615> — fix in progress at
<https://github.com/nikitabobko/AeroSpace/pull/2180>.

Any read-only `aerospace` CLI call forces a refresh + re-layout, so we nudge it:

| Piece | What it does |
|---|---|
| `aerospace-retile.sh` | On focus change: 3 quick refreshes over 0.5s (instant creation re-tile). Kill-restart, single instance. |
| `aerospace-poll.sh` | Background: refresh every 0.5s (covers same-app closes, which never emit an event). Skips while Nuvio is frontmost so video doesn't stutter. Started by `after-startup-command`. |

## When the upstream fix ships (check release notes for #1615 / #2180)

Remove, in BOTH `aerospace/` and `aerospace-docked/` variants of
`.config/aerospace/aerospace.toml`:

1. `after-startup-command`: the `aerospace-poll.sh` line
2. `on-focus-changed`: the `aerospace-retile.sh` line
3. `exec-on-workspace-change`: the trailing `; $HOME/dotfiles/aerospace-retile.sh &`
4. Delete `aerospace-retile.sh`, `aerospace-poll.sh`, and this file
5. Optionally re-enable the commented-out Chrome `move-node-to-workspace`
   rules in both variants (disabled because delayed detection made new Chrome
   windows visibly teleport) and the Nuvio float rule if tiled video works again

`pkill -f aerospace-poll.sh` after removing, or just restart AeroSpace.
