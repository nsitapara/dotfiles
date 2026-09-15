#!/bin/bash
# Apply the native-Space profile under the same lock as wm.sh and AeroSpace.
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
STATE="$HOME/.local/state/dotfiles-wm"
exec 9>"${TMPDIR:-/tmp}/.display-mode-state.lock"
lockf -s -t 10 9 || exit 1
launchctl list local.dotfiles.yabai >/dev/null 2>&1 || exit 0
mkdir -p "$STATE"

previous=""
settled=false
for attempt in 1 2 3 4 5; do
    plan=$("$HERE/display-layout.sh") || exit 1
    signature=$(jq -cS . <<< "$plan")
    if [ "$signature" = "$previous" ]; then settled=true; break; fi
    previous=$signature
    sleep 0.5
done
$settled || { echo 'Yabai display detection did not settle; will retry.' >&2; exit 1; }
count=$(jq 'length' <<< "$plan")
mode=non-docked
package=sketchybar
if [ "$count" -gt 1 ]; then mode=docked; package=sketchybar-docked; fi
pid=$(pgrep -x yabai)
# A new pin must re-apply even when it produces the same plan: picking a profile is also "apply now".
pin=$(cat "$STATE/display-profile.pin" 2>/dev/null || true)
signature=$(printf '%s\n%s\n%s\n' "$pid" "$signature" "$pin" | cksum)
live=$(readlink -f "$HOME/.config/sketchybar/sketchybarrc" 2>/dev/null || true)
bar_running=false
loaded=""
if pgrep -x sketchybar >/dev/null; then
    bar_running=true
    loaded=$(sketchybar --query display_mode 2>/dev/null |
        sed -nE 's/.*"value":[[:space:]]*"(docked|non-docked)".*/\1/p') || exit 1
    # Don't interrupt a bar reload in progress; the next event/interval retries.
    [ -n "$loaded" ] || exit 0
fi
old=$(cat "$STATE/display-profile.signature" 2>/dev/null || true)
if [ "$signature" = "$old" ] && [[ "$live" == *"/$package/.config/"* ]] &&
   { ! $bar_running || [ "$loaded" = "$mode" ]; }; then exit 0; fi

echo "Applying yabai $mode profile ($count active screens)"
if ! "$HERE/ensure-spaces.sh"; then
    echo 'Desktop creation unavailable; applying the display profile with existing desktops.' >&2
    "$HERE/spaces.sh"
fi
# The helper can take time to create Spaces. Don't record a different topology.
after=$("$HERE/display-layout.sh")
[ "$(jq -cS . <<< "$after")" = "$(jq -cS . <<< "$plan")" ] || {
    echo 'Displays changed during desktop setup; will retry.' >&2; exit 1;
}
spaces=$(yabai -m query --spaces)
while IFS=$'\t' read -r index top; do
    yabai -m config --space "$index" top_padding "$top"
done < <(jq -nr --argjson spaces "$spaces" --argjson plan "$plan" '
    $spaces[] | select(."is-native-fullscreen" == false) as $space |
    $plan[] | select(.index == $space.display) | [$space.index,.top_padding] | @tsv')

# Only the bar changes Stow packages. AeroSpace's config is left alone.
if [[ "$live" != *"/$package/.config/"* ]]; then
    stow --dir="$ROOT" --target="$HOME" -D sketchybar sketchybar-docked
    stow --dir="$ROOT" --target="$HOME" "$package"
fi
temp=$(mktemp "$STATE/display-layout.XXXXXX")
printf '%s\n' "$plan" > "$temp"
mv "$temp" "$STATE/display-layout.json"
if $bar_running; then
    sketchybar --reload "$HOME/.config/sketchybar/sketchybarrc"
    loaded=""
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        loaded=$(sketchybar --query display_mode 2>/dev/null |
            sed -nE 's/.*"value":[[:space:]]*"(docked|non-docked)".*/\1/p') || true
        [ "$loaded" = "$mode" ] && break
        sleep 0.5
    done
    [ "$loaded" = "$mode" ] || { echo 'SketchyBar profile did not load; will retry.' >&2; exit 1; }
fi
printf '%s\n' "$signature" > "$STATE/display-profile.signature"
