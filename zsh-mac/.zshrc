[ -f /opt/homebrew/etc/profile.d/autojump.sh ] && . /opt/homebrew/etc/profile.d/autojump.sh
 export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion
export PATH="$HOME/.local/bin:$PATH"


# FZF colors loaded from Omarchy theme
source ~/.config/omarchy/current/fzf-colors.sh

# CHANGE TO PROD IF NEED TO USE PROD OR OVERRIDE LOCAL SESSION
export AWS_PROFILE=dev

alias pp="$HOME/Documents/web-platform/scripts/prep_push.sh"
alias rt="cd $HOME/Documents/web-platform && just reset --many --report=0" 
alias mm="cd $HOME/Documents/web-platform && just lman makemigrations"
alias ds="cd $HOME/Documents/web-platform && docker compose up -d"
alias dsr="cd $HOME/Documents/web-platform && docker compose up --remove-orphans --build -d"
alias dal="cd $HOME/Documents/web-platform && docker compose logs --follow api"
alias as="cd $HOME/Documents/web-platform && pnpm dev"
alias copy_aws_creds="aws configure export-credentials --format env | sed 's/^export //'"
alias pw_config="cursor ~/Documents/web-platform/apps/staff/e2e/debug-config.json"

# eza aliases (modern ls replacement)
alias ls="eza --icons --git"
alias ll="eza -l --icons --git"
alias la="eza -la --icons --git"
alias lt="eza --tree --icons"
alias j="z"

revert() { git checkout dev -- "$@"; }

ff() {
  aerospace list-windows --all \
    | awk -F'\t' '{print $1 "\t" $0}' \
    | fzf --with-nth=2.. \
          --bind 'enter:execute(aerospace focus --window-id {1})+abort'
}

# https://github.com/eza-community/eza/blob/main/INSTALL.md
if type brew &>/dev/null; then
    FPATH="$(brew --prefix)/share/zsh/site-functions:${FPATH}"
    autoload -Uz compinit
    compinit
fi


# fzf tab configs
autoload -U compinit; compinit
source ~/Documents/fzf-tab/fzf-tab.plugin.zsh
# Enable fzf-tab to use FZF_DEFAULT_OPTS colors
zstyle ':fzf-tab:*' use-fzf-default-opts yes


eval "$(starship init zsh)"
eval "$(zoxide init zsh)"

. "$HOME/.atuin/bin/env"

eval "$(atuin init zsh)"


zatuin_run_selected() {
  emulate -L zsh
  set -o pipefail

  local outfile cmd rc
  outfile=$(mktemp -t atuinsel.XXXXXX) || { print -u2 "mktemp failed"; return 1; }
  trap 'rm -f "$outfile"' EXIT INT TERM

  # Forward all args to  atuin search
  if ! atuin search -i "$@" 2>"$outfile"; then
    rc=$?
  fi

  cmd=$(<"$outfile")
  rm -f "$outfile"; trap - EXIT INT TERM

  if [[ -n "$cmd" ]]; then
    print -r -- "Loaded into buffer: $cmd"
    print -z -- "$cmd"     # put into the ZLE buffer for editing
    return 0
  else
    print "No command selected."
    return ${rc:-0}
  fi
}

# Your alias can stay exactly like this:
alias hh='zatuin_run_selected'

alias copy_aws_creds="aws configure export-credentials --format env | sed 's/^export //' | tee /dev/tty | pbcopy"


# https://yazi-rs.github.io/docs/quick-start
function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ -n "$cwd" ] && [ "$cwd" != "$PWD" ] && builtin cd -- "$cwd"
	rm -f -- "$tmp"
}