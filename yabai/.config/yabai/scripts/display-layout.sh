#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$HERE/build-spaces-helper.sh"
metadata=$("$HOME/Applications/Dotfiles Spaces.app/Contents/MacOS/Dotfiles Spaces" --display-info)
if [ "${1:-}" = --aerospace ]; then
    monitors=$(aerospace list-monitors --format '%{monitor-id}|%{monitor-name}')
    displays=$(jq -Rn --argjson metadata "$metadata" '
      [inputs | split("|") | {index:(.[0]|tonumber),name:.[1]}] |
      map(. as $monitor | [$metadata[] | select(.name == $monitor.name)] as $matches |
        if ($matches|length) != 1 then error("Cannot uniquely match AeroSpace monitor name")
        else $matches[0] + {index:$monitor.index} end)' <<< "$monitors")
else
    displays=$(yabai -m query --displays)
fi
jq -e --argjson metadata "$metadata" '
  map(. as $display | [$metadata[] | select(.id == $display.id)][0] as $meta |
    if $meta == null then error("Display metadata has not settled") else . + $meta end)
' <<< "$displays" |
  jq -e --argjson prefs "$(cat "$HERE/../display-preferences.json")" -f "$HERE/display-layout.jq"
