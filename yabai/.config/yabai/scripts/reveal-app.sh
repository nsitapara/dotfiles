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
# Spotify's close button orders its window out without destroying it, so yabai
# still lists it and the cases above miss it. Send the reopen a Dock click sends.
# Windows on other Spaces stay ordered in, so switches to them never reopen.
closed=$(jq -r --argjson pid "$1" '[.[] | select(.pid == $pid)] |
  select(length > 0 and all(.[]; .["is-visible"] or .["is-minimized"] or .["is-hidden"] | not)) | .[].id' <<< "$windows")
# The check exits 0 only when every one of these windows is ordered out.
if [ -n "$closed" ] && /usr/bin/python3 - $closed <<'EOF'
import ctypes, sys
sl = ctypes.CDLL('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
cid, flag = sl.SLSMainConnectionID(), ctypes.c_uint8()
sys.exit(any(sl.SLSWindowIsOrderedIn(cid, int(w), ctypes.byref(flag)) == 0 and flag.value
             for w in sys.argv[1:]))
EOF
then
    open -b "$(osascript -e "tell application \"System Events\" to get bundle identifier of (first process whose unix id is $1)")"
fi
