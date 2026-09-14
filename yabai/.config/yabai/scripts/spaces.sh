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
      if ($ds | length) == 1 and ($ss | length) >= 6 then
        [$ss | sort_by(.index) | .[:6] | to_entries[] | {index:.value.index, label:("ws" + ((.key+1)|tostring))}]
      elif ($ds | length) == 2 then
        [$ss[] | select(.display == $ds[0].index)] | sort_by(.index) as $left |
        [$ss[] | select(.display == $ds[1].index)] | sort_by(.index) as $right |
        if ($left|length) >= 3 and ($right|length) >= 3 then
          [range(0;3) as $i |
            {index:$left[$i].index,label:("ws" + (($i*2+1)|tostring))},
            {index:$right[$i].index,label:("ws" + (($i*2+2)|tostring))}]
        else error("Create three native desktops on each monitor in Mission Control.") end
      else error("Create six native desktops on one monitor, or use two monitors with three each.") end
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

# Routing follows the active docked profile. Rules affect newly opened windows.
yabai -m rule --add label=dotfiles-dev app='^(Warp|PyCharm)$' space=ws1
yabai -m rule --add label=dotfiles-collaboration app='^(GitHub Desktop|Slack)$' space=ws2
echo "Workspaces ws1-ws6 ready. Cmd+1 through Cmd+6 select them."
