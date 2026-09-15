#!/bin/bash
# Cmd+Tab can make a hidden app frontmost without unhiding it. Force it visible.
# Usage: unhide-app.sh PID   (no-op when the app is already visible)
exec osascript -e "tell application \"System Events\" to set visible of (first process whose unix id is $1) to true"
