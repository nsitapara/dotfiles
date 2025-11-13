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
    echo "  brew install stow"
    echo "  brew install --cask nikitabobko/tap/aerospace"
    echo "  brew install sketchybar"
    exit 1
fi

echo -e "${GREEN}✓ All dependencies found${NC}"
echo ""

# Check for required directories
echo "Checking configuration directories..."
REQUIRED_DIRS=("aerospace" "aerospace-docked" "sketchybar" "sketchybar-docked")
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
    echo "Setting up automatic mode (LaunchAgent)..."

    CURRENT_USER=$(whoami)
    HOME_DIR="$HOME"

    if [ ! -f "$SCRIPT_DIR/com.user.display-mode-switcher.plist" ]; then
        echo -e "${RED}ERROR: com.user.display-mode-switcher.plist not found${NC}"
        exit 1
    fi

    # Create a temporary plist with updated paths
    sed "s|/Users/nishsitapara|$HOME_DIR|g" "$SCRIPT_DIR/com.user.display-mode-switcher.plist" > /tmp/display-switcher-temp.plist

    # Copy to LaunchAgents directory
    mkdir -p "$HOME_DIR/Library/LaunchAgents"
    cp /tmp/display-switcher-temp.plist "$HOME_DIR/Library/LaunchAgents/com.user.display-mode-switcher.plist"
    rm /tmp/display-switcher-temp.plist

    # Unload existing agent if it exists
    launchctl unload "$HOME_DIR/Library/LaunchAgents/com.user.display-mode-switcher.plist" 2>/dev/null || true

    # Load the LaunchAgent
    launchctl load "$HOME_DIR/Library/LaunchAgents/com.user.display-mode-switcher.plist"

    # Check if it loaded successfully
    if launchctl list | grep -q "com.user.display-mode-switcher"; then
        echo -e "${GREEN}✓ LaunchAgent installed and running${NC}"
        echo ""
        echo "========================================"
        echo -e "${GREEN}Setup Complete!${NC}"
        echo "========================================"
        echo ""
        echo "Automatic mode is now enabled."
        echo "The switcher will check every 30 seconds for display changes."
        echo ""
        echo "Commands:"
        echo "  Run manually:  $SCRIPT_DIR/switch-display-mode.sh"
        echo "  View logs:     tail -f /tmp/display-mode-switcher.log"
        echo "  Disable auto:  launchctl unload ~/Library/LaunchAgents/com.user.display-mode-switcher.plist"
        echo ""
    else
        echo -e "${RED}ERROR: Failed to load LaunchAgent${NC}"
        exit 1
    fi
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
