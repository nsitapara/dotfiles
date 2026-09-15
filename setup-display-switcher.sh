#!/bin/bash

# Setup script for automatic display mode switcher
# This script installs and configures the display mode switcher on a new machine

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
AUTO_MODE=false
for arg in "$@"; do
    case $arg in
        --auto|-a)
            AUTO_MODE=true
            shift
            ;;
        --help|-h)
            echo "Display Mode Switcher Setup"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -a, --auto    Enable automatic switching via LaunchAgent"
            echo "  -h, --help    Show this help message"
            echo ""
            echo "Without --auto flag, only the manual script will be set up."
            echo "You can enable automatic mode later by running:"
            echo "  $0 --auto"
            exit 0
            ;;
    esac
done

echo "========================================"
echo "Display Mode Switcher Setup"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check for required dependencies
echo "Checking dependencies..."
echo ""

MISSING_DEPS=()

if ! command -v stow &> /dev/null; then
    echo -e "${YELLOW}⚠ stow not found${NC}"
    MISSING_DEPS+=("stow")
fi

if ! command -v jq &> /dev/null; then
    MISSING_DEPS+=("jq")
fi

if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠ homebrew not found${NC}"
    MISSING_DEPS+=("homebrew")
fi

if ! command -v aerospace &> /dev/null; then
    echo -e "${YELLOW}⚠ aerospace not found${NC}"
    MISSING_DEPS+=("aerospace")
fi

if ! command -v sketchybar &> /dev/null; then
    echo -e "${YELLOW}⚠ sketchybar not found${NC}"
    MISSING_DEPS+=("sketchybar")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Missing required dependencies:${NC}"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "  - $dep"
    done
    echo ""
    echo "Please install missing dependencies:"
    echo "  brew install stow jq"
    echo "  brew install --cask nikitabobko/tap/aerospace"
    echo "  brew install sketchybar"
    exit 1
fi

echo -e "${GREEN}✓ All dependencies found${NC}"
echo ""

# Check for required directories
echo "Checking configuration directories..."
REQUIRED_DIRS=("aerospace" "aerospace-docked" "sketchybar" "sketchybar-docked" "yabai")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$SCRIPT_DIR/$dir" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -gt 0 ]; then
    echo -e "${RED}ERROR: Missing required configuration directories:${NC}"
    for dir in "${MISSING_DIRS[@]}"; do
        echo "  - $dir"
    done
    exit 1
fi

echo -e "${GREEN}✓ All required directories found${NC}"
echo ""

"$SCRIPT_DIR/yabai/.config/yabai/scripts/build-spaces-helper.sh"

# Make the switch script executable
echo "Setting up display mode switcher script..."
if [ -f "$SCRIPT_DIR/switch-display-mode.sh" ]; then
    chmod +x "$SCRIPT_DIR/switch-display-mode.sh"
    echo -e "${GREEN}✓ Script made executable${NC}"
else
    echo -e "${RED}ERROR: switch-display-mode.sh not found${NC}"
    exit 1
fi
echo ""

# Install LaunchAgent if --auto flag is passed
if [ "$AUTO_MODE" = true ]; then
    # Use the same installer as wm.sh; never recreate a separate polling job.
    /usr/bin/python3 "$SCRIPT_DIR/wm-startup.py" install
    echo "Desktop service enabled. It starts the saved manager and checks displays every 30 seconds."
    echo "Disable with: $SCRIPT_DIR/wm.sh default off"

else
    echo "========================================"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo "========================================"
    echo ""
    echo "Manual mode is ready."
    echo ""
    echo "To switch display modes, run:"
    echo -e "  ${BLUE}$SCRIPT_DIR/switch-display-mode.sh${NC}"
    echo ""
    echo -e "${YELLOW}💡 Want automatic switching?${NC}"
    echo "Run setup again with the --auto flag to enable LaunchAgent:"
    echo -e "  ${BLUE}$SCRIPT_DIR/setup-display-switcher.sh --auto${NC}"
    echo ""
    echo "This will automatically switch configs when you dock/undock."
    echo ""
fi
