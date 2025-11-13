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

# Check if mode has changed
if [ -f "$STATE_FILE" ]; then
    CURRENT_MODE=$(cat "$STATE_FILE")
    if [ "$CURRENT_MODE" = "$MODE" ]; then
        # No change, exit silently
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

# Restart sketchybar
if pgrep -x "sketchybar" > /dev/null; then
    brew services restart sketchybar
    echo "Sketchybar restarted"
else
    echo "Sketchybar is not running, skipping restart"
fi

echo ""
echo "✓ Successfully switched to $MODE mode"

# Save current mode to state file
echo "$MODE" > "$STATE_FILE"
