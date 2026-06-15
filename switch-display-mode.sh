#!/bin/bash

# Script to switch between docked and non-docked configurations
# Detects number of displays and stows appropriate configs

set -e

DOTFILES_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DOTFILES_DIR"

STATE_FILE="/tmp/.display-mode-state"

# Detect number of displays
DISPLAY_COUNT=$(system_profiler SPDisplaysDataType | grep -c "Resolution:" || echo "0")

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
    local live
    live=$(readlink -f "$HOME/.config/aerospace/aerospace.toml" 2>/dev/null)
    [[ "$live" == *"/$AEROSPACE_PKG/.config/"* ]]
}

# Check if mode has changed AND the config is already correctly stowed
if [ -f "$STATE_FILE" ]; then
    CURRENT_MODE=$(cat "$STATE_FILE")
    if [ "$CURRENT_MODE" = "$MODE" ] && live_config_matches; then
        # No change and config already correct, exit silently
        exit 0
    fi
fi

echo "Detected $DISPLAY_COUNT display(s)"
echo "Switching to $MODE mode"

echo ""
echo "Unstowing all display configurations..."

# Unstow all aerospace and sketchybar configs
stow -D aerospace 2>/dev/null || true
stow -D aerospace-docked 2>/dev/null || true
stow -D sketchybar 2>/dev/null || true
stow -D sketchybar-docked 2>/dev/null || true

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
# (newly stowed) config and rebuilds every item.
if pgrep -x "sketchybar" > /dev/null; then
    sketchybar --reload
    echo "Sketchybar reloaded"
else
    echo "Sketchybar is not running, skipping restart"
fi

echo ""
echo "✓ Successfully switched to $MODE mode"

# Save current mode to state file
echo "$MODE" > "$STATE_FILE"
