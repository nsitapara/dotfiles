# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# Load omarchy-zsh configuration
if [[ -d /usr/share/omarchy-zsh/conf.d ]]; then
  for config in /usr/share/omarchy-zsh/conf.d/*.zsh; do
    [[ -f "$config" ]] && source "$config"
  done
fi

# Load omarchy-zsh functions and aliases
if [[ -d /usr/share/omarchy-zsh/functions ]]; then
  for func in /usr/share/omarchy-zsh/functions/*.zsh; do
    [[ -f "$func" ]] && source "$func"
  done
fi

# Add your own customizations below
#

export OMARCHY_PATH=$HOME/.local/share/omarchy
export PATH=$OMARCHY_PATH/bin:$PATH:$HOME/.local/bin

# ── FZF colors (from theme) ──────────────────────────────
if [[ -f ~/.config/omarchy/current/fzf-colors.sh ]]; then
  source ~/.config/omarchy/current/fzf-colors.sh
else
  export FZF_DEFAULT_OPTS=" \
  --color=bg+:#313244,bg:#1E1E2E,spinner:#F5E0DC,hl:#F38BA8 \
  --color=fg:#CDD6F4,header:#F38BA8,info:#CBA6F7,pointer:#F5E0DC \
  --color=marker:#B4BEFE,fg+:#CDD6F4,prompt:#CBA6F7,hl+:#F38BA8 \
  --color=selected-bg:#45475A \
  --color=border:#6C7086,label:#CDD6F4"
fi

autoload -U compinit; compinit
source ~/Documents/fzf-tab/fzf-tab.plugin.zsh

# Enable fzf-tab to use FZF_DEFAULT_OPTS colors
zstyle ':fzf-tab:*' use-fzf-default-opts yes

# ── eza aliases ───────────────────────────────────────────
if command -v eza &> /dev/null; then
  alias ls='eza -lh --group-directories-first --icons=auto'
  alias lsa='ls -a'
  alias lt='eza --tree --level=2 --long --icons --git'
  alias lta='lt -a'
fi

# ── zoxide ────────────────────────────────────────────────
if command -v zoxide &> /dev/null; then
  eval "$(zoxide init zsh)"
  alias j='z'
fi

# ── starship prompt ───────────────────────────────────────
if command -v starship &> /dev/null; then
  eval "$(starship init zsh)"
fi

# ── atuin ─────────────────────────────────────────────────
. "$HOME/.atuin/bin/env"
eval "$(atuin init zsh)"

# https://yazi-rs.github.io/docs/quick-start
function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ -n "$cwd" ] && [ "$cwd" != "$PWD" ] && builtin cd -- "$cwd"
	rm -f -- "$tmp"
}
