#!/bin/bash

# Script to switch between docked and non-docked configurations
# Detects number of displays and stows appropriate configs

set -e

DOTFILES_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DOTFILES_DIR"

STATE_FILE="${TMPDIR:-/tmp}/.display-mode-state"
DISPLAY_STATE_FILE="${STATE_FILE}.displays"

# Serialize launchd and display-change runs without killing a switch midway.
# macOS releases this descriptor lock even if the process exits unexpectedly.
exec 9>"${STATE_FILE}.lock"
lockf -s -t 10 9 || exit 1

# Require two matching, nonzero readings while macOS settles after hotplug.
# Missing/failed detection must never be interpreted as a laptop-only layout.
PREVIOUS_SIGNATURE=""
DISPLAY_COUNT=0
for attempt in 1 2 3 4 5; do
    DISPLAY_INFO=$(system_profiler SPDisplaysDataType) || exit 1
    COUNT=$(printf '%s\n' "$DISPLAY_INFO" | awk '/Resolution:/ { n++ } END { print n+0 }')
    DISPLAY_LAYOUT=""
    if pgrep -x "sketchybar" > /dev/null; then
        DISPLAY_LAYOUT=$(sketchybar --query displays) || exit 1
        [ -n "$DISPLAY_LAYOUT" ] || exit 1
    fi
    # Include display identities and geometry, not just the count: replacing a
    # monitor or rearranging two monitors must refresh the docked assignments.
    DISPLAY_SIGNATURE=$(printf '%s\n%s\n' "$DISPLAY_INFO" "$DISPLAY_LAYOUT" | cksum)
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

# This item is added at the end of each Lua config. Symlinks and the state file
# alone cannot prove that the running bar successfully loaded the new profile.
bar_config_matches() {
    sketchybar --query display_mode 2>/dev/null |
        grep -q '"value": "'"$MODE"'"'
}

# Check the files AND the loaded profile before treating a run as a no-op.
if [ -f "$STATE_FILE" ]; then
    CURRENT_MODE=$(cat "$STATE_FILE")
    CURRENT_DISPLAYS=$(cat "$DISPLAY_STATE_FILE" 2>/dev/null || true)
    if [ "$CURRENT_MODE" = "$MODE" ] && [ "$CURRENT_DISPLAYS" = "$DISPLAY_SIGNATURE" ] && live_config_matches; then
        if ! pgrep -x "sketchybar" > /dev/null || bar_config_matches; then
            exit 0
        fi
    fi
fi

echo "Detected $DISPLAY_COUNT display(s)"
echo "Switching to $MODE mode"

echo ""
echo "Unstowing all display configurations..."

# Unstow all aerospace and sketchybar configs
stow -D aerospace
stow -D aerospace-docked
stow -D sketchybar
stow -D sketchybar-docked

echo "Unstowing complete."
echo ""
echo "Stowing $MODE configurations..."

# Stow the appropriate configs
stow "$AEROSPACE_PKG"
stow "$SKETCHYBAR_PKG"

echo "Stowing complete."
echo ""
echo "Restarting aerospace and sketchybar..."

# Restart aerospace
if pgrep -x "AeroSpace" > /dev/null; then
    aerospace reload-config
    echo "Aerospace config reloaded"
else
    echo "Aerospace is not running, skipping restart"
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
echo "$DISPLAY_SIGNATURE" > "$DISPLAY_STATE_FILE"
