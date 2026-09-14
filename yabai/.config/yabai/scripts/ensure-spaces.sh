#!/bin/bash
set -euo pipefail
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Serialize callers from startup, reload, and the bar. lockf uses a descriptor.
exec 8>"${TMPDIR:-/tmp}/.dotfiles-create-spaces.lock"
lockf -s -t 20 8 || { echo 'Desktop setup is already running.' >&2; exit 1; }
"$HERE/build-spaces-helper.sh"
result=$(mktemp "${TMPDIR:-/tmp}/dotfiles-spaces.XXXXXX")
trap 'rm -f "$result"' EXIT
# Launch as an app so macOS grants permission to this helper, not the terminal.
open -W -n -g "$HOME/Applications/Dotfiles Spaces.app" --args "$(command -v yabai)" "$result"
if ! grep -q '^OK ' "$result"; then
    cat "$result" >&2
    echo 'Automatic desktop setup did not finish.' >&2
    exit 1
fi
cat "$result"
"$HERE/spaces.sh"
