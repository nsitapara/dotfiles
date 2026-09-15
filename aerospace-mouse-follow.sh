#!/bin/zsh
# A bar click temporarily suppresses focus-driven pointer movement.
zmodload zsh/datetime
marker="$HOME/.local/state/dotfiles-wm/bar-mouse-suppressed"
if [[ -r "$marker" ]]; then
    read -r click_pid click_deadline < "$marker"
    if [[ "$click_pid" == <-> && "$click_deadline" == <->.<-> ]] &&
       (( EPOCHREALTIME < click_deadline )) && kill -0 "$click_pid" 2>/dev/null; then
        exit 0
    fi
fi
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
exec aerospace move-mouse "${1:?Missing mouse target}"
