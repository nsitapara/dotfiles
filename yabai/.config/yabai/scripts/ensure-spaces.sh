#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Serialize callers from startup, reload, and the bar. lockf uses a descriptor.
exec 8>"${TMPDIR:-/tmp}/.dotfiles-create-spaces.lock"
lockf -s -t 20 8 || { echo 'Desktop setup is already running.' >&2; exit 1; }
"$HERE/build-spaces-helper.sh"
result=$(mktemp "${TMPDIR:-/tmp}/dotfiles-spaces.XXXXXX")
plan=$(mktemp "${TMPDIR:-/tmp}/dotfiles-layout.XXXXXX")
trap 'rm -f "$result" "$plan"' EXIT
"$HERE/display-layout.sh" > "$plan"
# Launch as an app so macOS grants permission to this helper, not the terminal.
for attempt in 1 2; do
    # Hotplug/focus changes can dismiss Mission Control during a sweep. A fresh
    # helper reopens it and rechecks the topology and each desktop's occupancy.
    # Retry only missing UI controls, once; permission/layout failures need no UI loop.
    : > "$result"
    open -W -n -g "$HOME/Applications/Dotfiles Spaces.app" --args "$(command -v yabai)" "$result" "$plan"
    if grep -q '^OK ' "$result"; then break; fi
    if [ "$attempt" -eq 2 ] || ! grep -Eq '^ERROR (No thumbnail .*: no mc\.spaces\.list|Mission Control did not expose its Accessibility controls\.)$' "$result"; then
        break
    fi
    cat "$result" >&2
    echo 'Mission Control desktop controls disappeared; retrying desktop setup once.' >&2
    sleep 1
done
if ! grep -q '^OK ' "$result"; then
    cat "$result" >&2
    echo 'Automatic desktop setup did not finish.' >&2
    exit 1
fi
cat "$result"
"$HERE/spaces.sh" --plan "$plan" "$@"
