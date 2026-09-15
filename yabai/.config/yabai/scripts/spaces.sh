#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
spaces=$(yabai -m query --spaces)
displays=$(yabai -m query --displays)

# Existing labels survive monitor hotplug. Do not reshuffle a working session.
if ! jq -e '[.[] | select(.label | test("^ws[1-6]$"))] | length == 6' <<< "$spaces" >/dev/null; then
    # Sort physical positions, avoiding machine-specific UUIDs and display IDs.
    mapping=$(jq -nr --argjson spaces "$spaces" --argjson displays "$displays" '
      ($displays | sort_by(.frame.x, .frame.y)) as $ds |
      [$spaces[] | select(."is-native-fullscreen" == false)] as $ss |
      if ($ds | length) == 1 and ($ss | length) >= 1 then
        [$ss | sort_by(.index) | .[:6] | to_entries[] | {index:.value.index, label:("ws" + ((.key+1)|tostring))}]
      elif ($ds | length) == 2 then
        [$ss[] | select(.display == $ds[0].index)] | sort_by(.index) as $left |
        [$ss[] | select(.display == $ds[1].index)] | sort_by(.index) as $right |
        [range(0;3) as $i |
          (if $left[$i] then {index:$left[$i].index,label:("ws" + (($i*2+1)|tostring))} else empty end),
          (if $right[$i] then {index:$right[$i].index,label:("ws" + (($i*2+2)|tostring))} else empty end)]
      else error("Use one or two monitors for automatic desktop labels.") end
      | .[] | [.index,.label] | @tsv')
    # Validate all labels before mutating any of them.
    while IFS=$'\t' read -r index label; do
        old=$(jq -r --argjson index "$index" '.[] | select(.index == $index) | .label' <<< "$spaces")
        if [ -n "$old" ] && [ "$old" != "$label" ]; then
            echo "Desktop $index already has label $old; refusing to replace it." >&2
            exit 1
        fi
    done <<< "$mapping"
    while IFS=$'\t' read -r index label; do
        yabai -m space "$index" --label "$label"
    done <<< "$mapping"
fi

spaces=$(yabai -m query --spaces)
labels=$(jq -r '[.[] | .label | select(test("^ws[1-6]$"))] | sort | join(", ")' <<< "$spaces")
echo "Ready: $labels. Cmd+number selects the matching workspace."
if ! jq -e '[.[] | select(.label | test("^ws[1-6]$"))] | length == 6' <<< "$spaces" >/dev/null; then
    echo "For all six shortcuts, create six desktops on one display, or three on each of two displays, then run ./wm.sh spaces."
fi
