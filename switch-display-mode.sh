#!/bin/bash

# Script to switch between docked and non-docked configurations
# Detects number of displays and stows appropriate configs

set -e

DOTFILES_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DOTFILES_DIR"

# Login startup and periodic display checks share this named entry point.
# Dispatch before taking the display lock: wm.sh owns that lock and calls this
# script without --login after the selected manager is ready.
if [ "${1:-}" = --login ]; then
    case "${2:-}" in
        yabai|aerospace)
            [ "$#" -eq 2 ] || exit 64
            exec "$DOTFILES_DIR/wm.sh" "$2" ;;
        *) echo "Usage: $0 --login yabai|aerospace" >&2; exit 64 ;;
    esac
fi

STATE_FILE="${TMPDIR:-/tmp}/.display-mode-state"
DISPLAY_STATE_FILE="${STATE_FILE}.displays"
WORKSPACE_STATE_FILE="${STATE_FILE}.workspaces"

# Serialize launchd and display-change runs without killing a switch midway.
# macOS releases this descriptor lock even if the process exits unexpectedly.
exec 9>"${STATE_FILE}.lock"
lockf -s -t 10 9 || exit 1

# Native Spaces need different hotplug handling from AeroSpace workspaces.
if launchctl list local.dotfiles.yabai >/dev/null 2>&1; then
    exec 9>&-
    exec "$DOTFILES_DIR/yabai/.config/yabai/scripts/display-profile.sh"
fi

# Require two matching, nonzero readings while macOS settles after hotplug.
# Missing/failed detection must never be interpreted as a laptop-only layout.
PREVIOUS_SIGNATURE=""
DISPLAY_COUNT=0
for attempt in 1 2 3 4 5; do
    DISPLAY_INFO=$(LC_ALL=C system_profiler SPDisplaysDataType) || exit 1
    COUNT=$(printf '%s\n' "$DISPLAY_INFO" | awk '/Resolution:/ { n++ } END { print n+0 }')
    DISPLAY_LAYOUT=""
    if pgrep -x "sketchybar" > /dev/null; then
        DISPLAY_LAYOUT=$(sketchybar --query displays) || exit 1
        [ -n "$DISPLAY_LAYOUT" ] || exit 1
    fi
    # Human-readable profiler output includes changing refresh-rate/driver data.
    # Only the display count and SketchyBar's identities/geometry affect pinning.
    DISPLAY_SIGNATURE=$(printf '%s\n%s\n' "$COUNT" "$DISPLAY_LAYOUT" | cksum)
    if [ "$COUNT" -gt 0 ] && [ "$DISPLAY_SIGNATURE" = "$PREVIOUS_SIGNATURE" ]; then
        DISPLAY_COUNT=$COUNT
        break
    fi
    PREVIOUS_SIGNATURE=$DISPLAY_SIGNATURE
    sleep 0.5
done
if [ "$DISPLAY_COUNT" -eq 0 ]; then
    echo "Display detection did not settle; leaving the current profile unchanged" >&2
    exit 1
fi

WORKSPACE_PLAN=""
if pgrep -x AeroSpace >/dev/null; then
    WORKSPACE_PLAN=$("$DOTFILES_DIR/yabai/.config/yabai/scripts/display-layout.sh" --aerospace) || exit 1
    WORKSPACE_SIGNATURE=$(printf '%s\n%s\n' "$(pgrep -x AeroSpace)" "$(jq -cS . <<< "$WORKSPACE_PLAN")" | cksum)
fi

# Determine if docked (2+ displays) or not (1 display)
if [ "$DISPLAY_COUNT" -ge 2 ]; then
    MODE="docked"
    AEROSPACE_PKG="aerospace-docked"
    SKETCHYBAR_PKG="sketchybar-docked"
else
    MODE="non-docked"
    AEROSPACE_PKG="aerospace"
    SKETCHYBAR_PKG="sketchybar"
fi

# Verify the actually-stowed config matches the expected mode. Relying on the
# state file alone is not enough: if the file says e.g. "non-docked" but the
# docked packages are still stowed (a desync), the old early-exit would never
# correct it. This checks where the live config symlink really points.
live_config_matches() {
    local live live_bar
    live=$(readlink -f "$HOME/.config/aerospace/aerospace.toml" 2>/dev/null)
    live_bar=$(readlink -f "$HOME/.config/sketchybar/sketchybarrc" 2>/dev/null)
    [[ "$live" == *"/$AEROSPACE_PKG/.config/"* ]] &&
        [[ "$live_bar" == *"/$SKETCHYBAR_PKG/.config/"* ]]
}

# An unavailable marker can mean the bar is starting or busy. That is not
# evidence of a different profile; wait for the next check instead of resetting it.
bar_mode() {
    sketchybar --query display_mode 2>/dev/null |
        sed -nE 's/.*"value":[[:space:]]*"(docked|non-docked)".*/\1/p'
}
bar_config_matches() {
    [ "$(bar_mode)" = "$MODE" ]
}

CONFIG_CHANGED=false
live_config_matches || CONFIG_CHANGED=true
BAR_RUNNING=false
LOADED_MODE=""
if pgrep -x "sketchybar" > /dev/null; then
    BAR_RUNNING=true
    [ -n "$DISPLAY_LAYOUT" ] || exit 0
    LOADED_MODE=$(bar_mode)
    case "$LOADED_MODE" in
        docked|non-docked) ;;
        *) exit 0 ;;
    esac
fi

CURRENT_DISPLAYS=$(cat "$DISPLAY_STATE_FILE" 2>/dev/null || true)
REASON=""
if $CONFIG_CHANGED; then
    REASON="profile symlinks differ"
elif $BAR_RUNNING && [ "$LOADED_MODE" != "$MODE" ]; then
    REASON="loaded profile differs"
elif $BAR_RUNNING && [ -n "$CURRENT_DISPLAYS" ] && [ "$CURRENT_DISPLAYS" != "$DISPLAY_SIGNATURE" ]; then
    REASON="display layout changed"
elif [ -n "$WORKSPACE_PLAN" ] && [ "$(cat "$WORKSPACE_STATE_FILE" 2>/dev/null || true)" != "$WORKSPACE_SIGNATURE" ]; then
    REASON="workspace monitor assignments changed"
fi

if [ -z "$REASON" ]; then
    # Missing state alone must not reset a correctly configured desktop. Never
    # replace the last running layout with a snapshot taken while the bar is down.
    if [ "$(cat "$STATE_FILE" 2>/dev/null || true)" != "$MODE" ]; then
        echo "$MODE" > "$STATE_FILE"
    fi
    if $BAR_RUNNING && [ "$CURRENT_DISPLAYS" != "$DISPLAY_SIGNATURE" ]; then
        echo "$DISPLAY_SIGNATURE" > "$DISPLAY_STATE_FILE"
    fi
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Applying $MODE ($DISPLAY_COUNT displays): $REASON"

# Touch symlinks only for an actual profile change. Restowing identical files
# triggers SketchyBar's config watcher in addition to our explicit reload.
if $CONFIG_CHANGED; then
    stow -D aerospace
    stow -D aerospace-docked
    stow -D sketchybar
    stow -D sketchybar-docked
    stow "$AEROSPACE_PKG"
    stow "$SKETCHYBAR_PKG"

    if pgrep -x "AeroSpace" > /dev/null; then
        aerospace reload-config
        echo "Aerospace config reloaded"
    fi
fi

# AeroSpace can move entire workspaces without the native-Space restrictions.
# Numeric patterns are AeroSpace's own monitor IDs, joined by display name.
if [ -n "$WORKSPACE_PLAN" ]; then
    assignments=$(aerospace list-workspaces --all --format '%{workspace}|%{monitor-id}')
    while IFS=$'\t' read -r workspace monitor; do
        current=$(awk -F'|' -v ws="$workspace" '$1 == ws {print $2}' <<< "$assignments")
        [ "$current" != "$monitor" ] || continue
        aerospace move-workspace-to-monitor --workspace "$workspace" "$monitor"
    done < <(jq -r '.[] | .index as $monitor | .workspaces[] | [.,$monitor] | @tsv' <<< "$WORKSPACE_PLAN")
    mkdir -p "$HOME/.local/state/dotfiles-wm"
    temp=$(mktemp "$HOME/.local/state/dotfiles-wm/display-layout.XXXXXX")
    printf '%s\n' "$WORKSPACE_PLAN" > "$temp"
    mv "$temp" "$HOME/.local/state/dotfiles-wm/display-layout.json"
fi

# Reload sketchybar. Note: `brew services restart sketchybar` fails when the
# felixkratz tap is untrusted, so use the in-process reload which re-runs the
# newly stowed config and rebuilds every item. Pass the path explicitly: a bare
# --reload reuses the previously resolved config path, even after Stow switches
# the symlink, leaving the docked display assignments active on the laptop.
if pgrep -x "sketchybar" > /dev/null; then
    sketchybar --reload "$HOME/.config/sketchybar/sketchybarrc"
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        bar_config_matches && break
        sleep 0.5
    done
    if ! bar_config_matches; then
        echo "Sketchybar did not load the $MODE profile; the next run will retry" >&2
        exit 1
    fi
    echo "Sketchybar reloaded"
else
    echo "Sketchybar is not running, skipping restart"
fi

echo ""
echo "✓ Successfully switched to $MODE mode"

# Save current mode to state file
echo "$MODE" > "$STATE_FILE"
if $BAR_RUNNING; then
    echo "$DISPLAY_SIGNATURE" > "$DISPLAY_STATE_FILE"
fi
if [ -n "$WORKSPACE_PLAN" ]; then echo "$WORKSPACE_SIGNATURE" > "$WORKSPACE_STATE_FILE"; fi
