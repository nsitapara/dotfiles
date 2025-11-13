# Automatic Display Mode Switcher

Automatically switches between docked and non-docked configurations for AeroSpace and Sketchybar based on the number of connected displays.

## Quick Start

```bash
# Install (manual mode)
./setup-display-switcher.sh

# Install with automatic switching
./setup-display-switcher.sh --auto

# Run manually anytime
./switch-display-mode.sh

# Remove automatic mode
launchctl unload ~/Library/LaunchAgents/com.user.display-mode-switcher.plist
rm ~/Library/LaunchAgents/com.user.display-mode-switcher.plist
```

## Overview

This tool detects the number of connected displays and automatically manages your dotfiles using GNU Stow:

- **Docked Mode** (2+ displays): Uses `aerospace-docked` and `sketchybar-docked` configurations
- **Non-Docked Mode** (1 display): Uses `aerospace` and `sketchybar` configurations

The switcher can run manually on-demand or automatically in the background (with `--auto` flag).

## Directory Structure

```
dotfiles/
├── aerospace/                      # Non-docked aerospace config
│   └── .config/aerospace/
├── aerospace-docked/               # Docked aerospace config
│   └── .config/aerospace/
├── sketchybar/                     # Non-docked sketchybar config
│   └── .config/sketchybar/
├── sketchybar-docked/              # Docked sketchybar config
│   └── .config/sketchybar/
├── switch-display-mode.sh          # Main switcher script
├── setup-display-switcher.sh      # Installation script
└── com.user.display-mode-switcher.plist  # LaunchAgent definition
```

## Requirements

- macOS
- [Homebrew](https://brew.sh/)
- [GNU Stow](https://www.gnu.org/software/stow/)
- [AeroSpace](https://github.com/nikitabobko/AeroSpace)
- [Sketchybar](https://github.com/FelixKratz/SketchyBar)

## Installation

### On a New Machine

1. Clone your dotfiles repository:
   ```bash
   git clone <your-dotfiles-repo> ~/dotfiles
   cd ~/dotfiles
   ```

2. Install dependencies (if not already installed):
   ```bash
   # Install Homebrew (if needed)
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   # Install required tools
   brew install stow
   brew install --cask nikitabobko/tap/aerospace
   brew install sketchybar
   ```

3. Run the setup script:

   **Manual mode only** (default):
   ```bash
   ./setup-display-switcher.sh
   ```

   **With automatic switching** (recommended):
   ```bash
   ./setup-display-switcher.sh --auto
   ```

The setup script will:
- Verify all dependencies are installed
- Check for required configuration directories
- Make scripts executable
- **If `--auto` flag is used**: Install and start the LaunchAgent for automatic switching

### Setup Options

```bash
./setup-display-switcher.sh [OPTIONS]

Options:
  -a, --auto    Enable automatic switching via LaunchAgent
  -h, --help    Show help message
```

**Without `--auto`**: Only sets up the manual script. You can run it manually whenever needed.

**With `--auto`**: Installs a LaunchAgent that automatically checks every 30 seconds and switches configs when you dock/undock.

**Enable auto mode later**: If you initially set up without `--auto`, you can enable it anytime by running:
```bash
./setup-display-switcher.sh --auto
```

### Important Notes

**Idempotency**: The setup script is idempotent and can be run multiple times safely:
- Running it multiple times won't cause errors or duplicate configurations
- Re-running with `--auto` will update and reload the LaunchAgent
- Safe to use when updating configurations or switching between machines

**Safe Operations**:
```bash
# These are all safe to run multiple times
./setup-display-switcher.sh         # Sets up manual mode again
./setup-display-switcher.sh --auto  # Reinstalls/updates automatic mode
```

## Usage

### Automatic Mode (with --auto flag)

Once installed with `--auto`, the switcher runs automatically:
- Checks every 30 seconds for display changes
- Switches configurations when you dock/undock
- Only restarts services when mode actually changes
- Runs on login

### Manual Mode

Run the switcher manually anytime:
```bash
~/dotfiles/switch-display-mode.sh
```

Or create a shell alias:
```bash
# Add to ~/.zshrc or ~/.bashrc
alias switch-display='~/dotfiles/switch-display-mode.sh'
```

## Monitoring

### View Logs (Automatic Mode Only)

If you enabled automatic mode with `--auto`:

```bash
# View all logs
cat /tmp/display-mode-switcher.log

# Follow logs in real-time
tail -f /tmp/display-mode-switcher.log

# View errors
cat /tmp/display-mode-switcher.err
```

### Check LaunchAgent Status (Automatic Mode Only)

If you enabled automatic mode:

```bash
# Check if running
launchctl list | grep display-mode

# Output explanation:
# - Exit code 0: Running successfully
# - Exit code 127: Missing PATH or commands not found
# - Other codes: Check error log
```

## Management

### Enable Automatic Switching

If you initially set up without `--auto` and want to enable it:

```bash
cd ~/dotfiles
./setup-display-switcher.sh --auto
```

### Disable Automatic Switching (Temporary)

If automatic mode is enabled and you want to disable it temporarily:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.display-mode-switcher.plist
```

The LaunchAgent file remains installed but won't run. Re-enable it with the command below.

### Re-enable Automatic Switching

If you disabled it and want to re-enable:

```bash
launchctl load ~/Library/LaunchAgents/com.user.display-mode-switcher.plist
```

### Remove Automatic Switching (Permanent)

To completely remove the LaunchAgent and automatic switching:

```bash
# Stop the LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.user.display-mode-switcher.plist 2>/dev/null || true

# Remove the LaunchAgent file
rm ~/Library/LaunchAgents/com.user.display-mode-switcher.plist

# Clean up log files (optional)
rm /tmp/display-mode-switcher.log 2>/dev/null || true
rm /tmp/display-mode-switcher.err 2>/dev/null || true
```

After removing, you can still use the manual script:
```bash
~/dotfiles/switch-display-mode.sh
```

Or re-enable automatic mode anytime:
```bash
cd ~/dotfiles
./setup-display-switcher.sh --auto
```

### Uninstall

```bash
# Stop and remove LaunchAgent (if automatic mode was enabled)
launchctl unload ~/Library/LaunchAgents/com.user.display-mode-switcher.plist 2>/dev/null || true
rm ~/Library/LaunchAgents/com.user.display-mode-switcher.plist 2>/dev/null || true

# Unstow all configs
cd ~/dotfiles
stow -D aerospace 2>/dev/null || true
stow -D aerospace-docked 2>/dev/null || true
stow -D sketchybar 2>/dev/null || true
stow -D sketchybar-docked 2>/dev/null || true

# Clean up state and log files
rm /tmp/.display-mode-state 2>/dev/null || true
rm /tmp/display-mode-switcher.log 2>/dev/null || true
rm /tmp/display-mode-switcher.err 2>/dev/null || true
```

## How It Works

1. **Detection**: Uses `system_profiler SPDisplaysDataType` to count connected displays
2. **State Tracking**: Maintains state in `/tmp/.display-mode-state` to avoid unnecessary switches
3. **Configuration Management**: Uses GNU Stow to symlink configs from dotfiles to `~/.config`
4. **Service Restart**:
   - AeroSpace: Uses `aerospace reload-config` for fast reload
   - Sketchybar: Uses `brew services restart` for full restart
5. **Automation**: macOS LaunchAgent checks every 30 seconds and triggers on login

## Customization

### Change Check Interval

Edit the `StartInterval` in the plist file before running setup:

```xml
<key>StartInterval</key>
<integer>30</integer>  <!-- Change to desired seconds -->
```

Then re-run `./setup-display-switcher.sh`

### Add More Configuration Packages

To add additional tools (e.g., different tmux configs):

1. Create directories:
   ```bash
   mkdir -p mytool mytool-docked
   ```

2. Add your configs using Stow structure:
   ```bash
   mytool/.config/mytool/config
   mytool-docked/.config/mytool/config
   ```

3. Edit `switch-display-mode.sh` to include your tool:
   ```bash
   # In the docked section
   MYTOOL_PKG="mytool-docked"

   # In the non-docked section
   MYTOOL_PKG="mytool"

   # In the unstow section
   stow -D mytool 2>/dev/null || true
   stow -D mytool-docked 2>/dev/null || true

   # In the stow section
   stow "$MYTOOL_PKG"
   ```

4. Update `setup-display-switcher.sh` to check for your directories

## Troubleshooting

### LaunchAgent Not Running

```bash
# Check status
launchctl list | grep display-mode

# If exit code is 127, PATH issue - verify in plist:
grep PATH ~/Library/LaunchAgents/com.user.display-mode-switcher.plist
```

### Configs Not Switching

```bash
# Run manually to see errors
~/dotfiles/switch-display-mode.sh

# Check state file
cat /tmp/.display-mode-state

# Reset state to force switch
rm /tmp/.display-mode-state
~/dotfiles/switch-display-mode.sh
```

### Stow Conflicts

```bash
# If stow complains about existing files
cd ~/dotfiles

# Unstow everything
stow -D aerospace aerospace-docked sketchybar sketchybar-docked

# Remove conflicting files manually
rm ~/.config/aerospace/aerospace.toml
rm ~/.config/sketchybar/sketchybarrc

# Try again
./switch-display-mode.sh
```

### Services Not Restarting

```bash
# Check if processes are running
pgrep -x AeroSpace
pgrep -x sketchybar

# Manual restart
aerospace reload-config
brew services restart sketchybar
```

## Files

- **switch-display-mode.sh**: Main script that detects displays and switches configs
- **setup-display-switcher.sh**: One-time setup script for new machines
- **com.user.display-mode-switcher.plist**: LaunchAgent definition for automation
- **/tmp/.display-mode-state**: Tracks current mode to avoid unnecessary switches
- **/tmp/display-mode-switcher.log**: Output log from automatic runs
- **/tmp/display-mode-switcher.err**: Error log from automatic runs

## Contributing

When adding this to a new machine or updating configurations:

1. Test manual switching first: `./switch-display-mode.sh`
2. Verify configs are correct for both modes
3. Check logs after setup: `tail -f /tmp/display-mode-switcher.log`
4. Test by connecting/disconnecting displays

## License

Part of personal dotfiles configuration.
