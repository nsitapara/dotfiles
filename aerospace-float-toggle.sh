#!/bin/bash
set -euo pipefail
# One Accessibility script per keypress; no watcher or persistent process.
exec /usr/bin/osascript -l JavaScript "$HOME/dotfiles/aerospace-float-toggle.js"
