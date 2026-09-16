#!/bin/bash
# Remember skhd's mode across bar reloads, scoped to the running daemon.
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
state="$HOME/.local/state/dotfiles-wm/skhd-mode"
pid=$(pgrep -x skhd || true)
if [ "${1:-get}" = get ]; then
    saved_pid= saved_mode=
    if [ -r "$state" ]; then read -r saved_pid saved_mode < "$state" || true; fi
    if [ -n "$pid" ] && [ "$saved_pid" = "$pid" ]; then
        echo "$saved_mode"
    else
        echo default
    fi
    exit 0
fi
case "$1" in default|resize|workspace|insertion|service) ;; *) exit 1 ;; esac
mkdir -p "$(dirname "$state")"
temp=$(mktemp "$state.XXXXXX")
trap 'rm -f "$temp"' EXIT
printf '%s %s\n' "$pid" "$1" > "$temp"
mv "$temp" "$state"
event=yabai_mode_changed
if launchctl list local.dotfiles.rift >/dev/null 2>&1; then event=rift_mode_changed; fi
sketchybar --trigger "$event" MODE="$1"
