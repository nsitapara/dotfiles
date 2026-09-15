#!/bin/bash
# Repair the display arrangement, then switch AeroSpace/sketchybar profiles —
# both driven off sketchybar's built-in display_change event.
#
# Why the arrangement needs repairing: a Screen Sharing session releases the
# physical displays and hands the session a virtual one. When it ends macOS
# re-attaches them scrambled — the built-in re-enumerates as an active display
# (and Main Display) even with the lid shut, and the externals come back stacked
# instead of side by side. Observed after one session: built-in at (0,0), LG at
# (-494,-1440), PA278QV at (1728,0). That leaves the two externals sharing only a
# 338pt corner, so the mouse can barely cross between them, and every monitor-
# relative AeroSpace command has to hop through a screen nobody can see.
#
# Why the profile switch needs this event: switch-display-mode.sh runs on a 30s
# launchd StartInterval, so until it fires the wrong profile stays stowed —
# workspaces force-assigned to a monitor that isn't there, space pills pinned to a
# dead display index. This makes it immediate; the launchd interval remains the
# backstop. Ordering matters: repair the arrangement first, so the profile switch
# and sketchybar's per-display pinning both read the corrected layout.
#
# Concurrent events share a lock and leave the pending run to finish. Never kill
# it: it may already be changing symlinks or reloading the apps.
# display_change also fires on focused-monitor changes;
# switch-display-mode.sh already exits early when the mode and stowed config match.

LOCK="${TMPDIR:-/tmp}/aerospace-monitor-sync.lock"
BIN=/opt/homebrew/bin

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFERENCES="$ROOT/yabai/.config/yabai/display-preferences.json"
# Optional physical arrangement repair is configured alongside workspace roles.
# A replacement monitor won't match these UUIDs; update the snapshot or disable it.
repair=$("$BIN/jq" -e '.clamshell_repair | select(.enabled)' "$PREFERENCES" 2>/dev/null) || repair='{}'
LG=$("$BIN/jq" -r '.odd_display_uuid // empty' <<< "$repair")
PA=$("$BIN/jq" -r '.even_display_uuid // empty' <<< "$repair")
BUILTIN=$("$BIN/jq" -r '.built_in_uuid // empty' <<< "$repair")
LG_SETTINGS=$("$BIN/jq" -r '.odd_settings // empty' <<< "$repair")
PA_SETTINGS=$("$BIN/jq" -r '.even_settings // empty' <<< "$repair")
LG_ORIGIN=$(printf '%s\n' "$LG_SETTINGS" | sed -nE 's/.*(origin:\([^)]*\)).*/\1/p')
PA_ORIGIN=$(printf '%s\n' "$PA_SETTINGS" | sed -nE 's/.*(origin:\([^)]*\)).*/\1/p')

# Keep output independent of the Lua callback, which exits when the bar reloads.
exec >>/tmp/display-mode-switcher.log 2>>/tmp/display-mode-switcher.err
exec 8>"$LOCK"
lockf -s -t 0 8 || exit 0

# macOS reports a new arrangement in stages; acting too early reads a
# half-applied layout. The switcher also checks for a stable display snapshot.
sleep 1.5

# Serialize with wm.sh before repairing displays. During a yabai trial, native
# Spaces own monitor placement; skip the AeroSpace-specific arrangement repair
# and let the shared switcher select the yabai profile instead.
exec 9>"${TMPDIR:-/tmp}/.display-mode-state.lock"
lockf -s -t 10 9 || exit 1
if launchctl list local.dotfiles.yabai >/dev/null 2>&1; then
    exec 9>&-
    exec "$ROOT/switch-display-mode.sh"
fi

# Only repair in clamshell with both externals back. Every other state — laptop
# alone, Screen Sharing's single virtual display, or the lid genuinely open — is a
# legitimate layout that must not be fought.
lid_closed() {
    ioreg -r -k AppleClamshellState -d 1 2>/dev/null | grep -q '"AppleClamshellState" = Yes'
}
# One screen's chunk of the `displayplacer list` command line, which quotes per screen.
segment() { printf '%s\n' "$2" | tr '"' '\n' | grep -m1 "id:$1"; }

current=$("$BIN/displayplacer" list 2>/dev/null | tail -1)
lg_seg=$(segment "$LG" "$current")
pa_seg=$(segment "$PA" "$current")
builtin_seg=$(segment "$BUILTIN" "$current")

if [ -n "$LG" ] && [ -n "$PA" ] && [ -n "$BUILTIN" ] &&
   [ -n "$LG_ORIGIN" ] && [ -n "$PA_ORIGIN" ] &&
   lid_closed && [ -n "$lg_seg" ] && [ -n "$pa_seg" ]; then
    # A disabled built-in counts as correct as much as an absent one does —
    # otherwise re-applying would never satisfy the check and would loop forever.
    builtin_ok=false
    { [ -z "$builtin_seg" ] || [[ "$builtin_seg" == *"enabled:false"* ]]; } && builtin_ok=true

    if ! { [[ "$lg_seg" == *"$LG_ORIGIN"* ]] && [[ "$pa_seg" == *"$PA_ORIGIN"* ]] && $builtin_ok; }; then
        # This emits another display_change; the check above makes that pass a
        # no-op rather than a loop.
        "$BIN/displayplacer" \
            "id:$LG $LG_SETTINGS" \
            "id:$PA $PA_SETTINGS" \
            "id:$BUILTIN enabled:false" >/dev/null 2>&1
        sleep 1.5   # let it settle before the profile switch reads the layout
    fi
fi

exec 9>&-
exec "$ROOT/switch-display-mode.sh"
