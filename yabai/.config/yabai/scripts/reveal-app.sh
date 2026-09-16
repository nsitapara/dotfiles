#!/bin/bash
# Cmd+Tab can make an app frontmost while it stays hidden or every window stays
# minimized. Bring it back like a Dock click would. Usage: reveal-app.sh PID
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
set -euo pipefail
[[ "${1:-}" =~ ^[1-9][0-9]*$ ]] || { echo 'Usage: reveal-app.sh PID' >&2; exit 1; }
windows=$(yabai -m query --windows)
actions=$(jq -r --argjson pid "$1" '
  [.[] | select(.pid == $pid)] |
  (if length == 0 or any(.[]; .["is-hidden"]) then "unhide" else empty end),
  (.[] | select(.["is-minimized"]) | .id)
' <<< "$windows")
# With no known windows, retain the old recovery for windowless hidden apps.
while IFS= read -r action; do
    case "$action" in
        unhide) osascript -e "tell application \"System Events\" to set visible of (first process whose unix id is $1) to true" ;;
        '') ;;
        *) yabai -m window --deminimize "$action" && yabai -m window --focus "$action" ;;
    esac
done <<< "$actions"
