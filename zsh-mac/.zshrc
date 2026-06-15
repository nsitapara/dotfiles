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

unalias copy_aws_creds 2>/dev/null
copy_aws_creds() {
  local creds
  creds=$(aws configure export-credentials --format env | sed 's/^export //') || return 1
  printf '%s\n' "$creds"
  printf '%s' "$creds" | pbcopy

  if [[ -f "$PWD/.env.secrets" ]]; then
    local file="$PWD/.env.secrets" tmp
    tmp=$(mktemp) || return 1
    while IFS= read -r line; do
      local key="${line%%=*}"
      if grep -q "^${key}=" "$file"; then
        awk -v k="$key" -v l="$line" 'BEGIN{FS=OFS="="} $1==k{print l; next} {print}' "$file" > "$tmp" && mv "$tmp" "$file"
      else
        printf '%s\n' "$line" >> "$file"
      fi
    done <<< "$creds"
    rm -f "$tmp"
    echo ""
    echo "✓ Copied to clipboard and updated $file"
  else
    echo ""
    echo "✓ Copied to clipboard"
    echo "ℹ No .env.secrets found in $PWD"
  fi
}


# https://yazi-rs.github.io/docs/quick-start
function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ -n "$cwd" ] && [ "$cwd" != "$PWD" ] && builtin cd -- "$cwd"
	rm -f -- "$tmp"
}

alias claude="claude --dangerously-skip-permissions"


# Quick worktree creation + cd
gtn() {
  local existing
  existing=$(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //' | grep "$1")
  if [[ -n "$existing" ]]; then
    cd "$existing"
  else
    git gtr new "$1" && cd "$(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //' | grep "$1")"
  fi
}

# fzf worktree switcher
gtc() {
  local selected
  selected=$(git worktree list --porcelain \
    | grep '^worktree ' \
    | sed 's/^worktree //' \
    | fzf --prompt="worktree> " --with-nth=-1 --delimiter='/')
  [[ -n "$selected" ]] && cd "$selected"
}

gtrm() {
  local selected
  selected=$(git worktree list --porcelain \
    | grep '^branch ' \
    | sed 's|^branch refs/heads/||' \
    | fzf --prompt="remove> ")
  [[ -n "$selected" ]] && git gtr rm "$selected"
}
# bun completions
[ -s "/Users/nishsitapara/.bun/_bun" ] && source "/Users/nishsitapara/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# Sync current branch with latest origin/dev
alias gmd='git fetch origin dev && git merge origin/dev'
alias ports='lsof -iTCP -sTCP:LISTEN -nP'

# AWS ECS shell helpers — sso login, set profile, exec into ApiContainer
ssh_aws_dev() {
  aws sso login --profile dev || return 1
  export AWS_PROFILE=dev
  "$HOME/Documents/web-platform/scripts/ecs_shell.sh" web-platform-cluster ApiContainer
}

ssh_aws_prod() {
  aws sso login --profile prod || return 1
  export AWS_PROFILE=prod
  "$HOME/Documents/web-platform/scripts/ecs_shell.sh" web-platform-cluster ApiContainer
}

# pnpm
export PNPM_HOME="/Users/nishsitapara/Library/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
# pnpm end

# >>> headroom docker-native >>>
export PATH="/Users/nishsitapara/.local/bin:$PATH"
# <<< headroom docker-native <<<
