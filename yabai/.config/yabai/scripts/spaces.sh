#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plan_file=""
check_only=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --plan) plan_file=$2; shift 2 ;;
        --check) check_only=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
if [ -n "$plan_file" ]; then plan=$(cat "$plan_file"); else plan=$("$HERE/display-layout.sh"); fi
spaces=$(yabai -m query --spaces)
# Assign only unlabelled desktops and labels owned by this setup. Native
# fullscreen and custom-labelled desktops remain untouched. A label already on
# the right display stays put; one on the wrong display moves to a free desktop
# there and takes its windows, since macOS keeps desktops on hotplug.
plan_json=$(jq -cn --argjson spaces "$spaces" --argjson plan "$plan" '
  [$spaces[] | select(."is-native-fullscreen" == false)
   | select(.label == "" or (.label | test("^ws[1-9]$")))] | sort_by(.index) as $ordinary |
  [$plan[] as $screen | $screen.workspaces[] | {label:("ws" + tostring), display:$screen.index}] as $wanted |
  [$wanted[] as $w | $ordinary[] | select(.label == $w.label and .display == $w.display)
   | {index,label}] as $kept |
  reduce ($wanted[] | select(.label as $l | $kept | all(.label != $l))) as $w ($kept;
    . as $taken |
    [$ordinary[] | select(.display == $w.display and (.index as $i | $taken | all(.index != $i)))
     | select(.label == "" or (.label as $l | $wanted | all(.label != $l)))][0] as $free |
    if $free == null then . else
      . + [{index:$free.index, label:$w.label,
            windows:[$ordinary[] | select(.label == $w.label) | (.windows // [])[]]}]
    end)
  | sort_by(.index)')
mapping=$(jq -c 'map({index,label})' <<< "$plan_json")
[ "$mapping" != '[]' ] || { echo 'No ordinary desktops are available to label.' >&2; exit 1; }
current=$(jq -c '[.[] | select(.label | test("^ws[1-9]$")) | {index,label}] | sort_by(.index)' <<< "$spaces")
if [ "$current" != "$mapping" ]; then
    if $check_only; then
        echo 'Workspace labels do not match the display profile.' >&2
        exit 1
    fi
    # Clear our old aliases first, avoiding collisions when swapping ws2/ws3.
    while read -r index; do
        [ -n "$index" ] && yabai -m space "$index" --label
    done < <(jq -r '.[].index' <<< "$current")
    while IFS=$'\t' read -r index label; do
        yabai -m space "$index" --label "$label"
    done < <(jq -r '.[] | [.index,.label] | @tsv' <<< "$mapping")
    while IFS=$'\t' read -r index label window; do
        if yabai -m window "$window" --space "$index" 2>/dev/null; then
            echo "Moved window $window to $label."
        fi
    done < <(jq -r '.[] | .index as $i | .label as $l | (.windows // [])[] | [$i,$l,.] | @tsv' <<< "$plan_json")
    # Label changes do not emit a window/focus event. Wake a bar that rejected
    # the intermediate startup snapshot, without requiring a Space switch.
    sketchybar --trigger yabai_windows_changed 2>/dev/null || true
fi
labels=$(jq -r '[.[].label] | sort | join(", ")' <<< "$mapping")
echo "Ready: $labels. Cmd+number selects the matching workspace."
expected=$(jq '[.[].workspaces[]] | length' <<< "$plan")
actual=$(jq 'length' <<< "$mapping")
if [ "$actual" -lt "$expected" ]; then
    echo "Run ./wm.sh spaces to create the remaining $((expected - actual)) desktops."
fi
