#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
case "${1:-}" in
    float)
        exec /usr/bin/python3 "$HOME/dotfiles/wm-float.py" ;;
    resize)
        exec /usr/bin/python3 "$HOME/dotfiles/wm-resize.py" "${2:?Missing resize axis}" "${3:?Missing resize delta}" ;;
    send-space)
        target=$(yabai -m query --spaces --space "${2:?Missing space}" | jq -er '.index')
        yabai -m window --space "$target" && yabai -m space --focus "$target" ;;
    send-display)
        selector=${2:?Missing display}
        if ! target=$(yabai -m query --displays --display "$selector" | jq -er '.index'); then
            case "$selector" in next) selector=first ;; prev) selector=last ;; *) exit 1 ;; esac
            target=$(yabai -m query --displays --display "$selector" | jq -er '.index')
        fi
        yabai -m window --display "$target" && yabai -m display --focus "$target" ;;
    layout)
        current=$(yabai -m query --spaces --space | jq -r '.type')
        if [ "$current" = stack ]; then yabai -m space --layout bsp; else yabai -m space --layout stack; fi ;;
    *) echo "Usage: window.sh float|resize width/height DELTA|send-space SPACE|send-display DISPLAY|layout" >&2; exit 1 ;;
esac
