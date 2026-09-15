#!/bin/bash
# Cmd+Tab can make an app frontmost while it stays hidden or every window stays
# minimized. Bring it back like a Dock click would. Usage: reveal-app.sh PID
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
osascript -e "tell application \"System Events\" to set visible of (first process whose unix id is $1) to true"
# ponytail: restores every minimized window of the app; Cmd+M is swallowed so this is rare.
for id in $(yabai -m query --windows | jq -r --argjson pid "$1" '.[] | select(.pid == $pid and .["is-minimized"]) | .id'); do
    yabai -m window --deminimize "$id" && yabai -m window --focus "$id"
done
