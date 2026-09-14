#!/bin/bash
# Install and switch window managers. Trial jobs exist only for this login.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"
STATE="${DOTFILES_WM_STATE_DIR:-$HOME/.local/state/dotfiles-wm}"
YABAI_JOB=local.dotfiles.yabai
SKHD_JOB=local.dotfiles.skhd

die() { echo "$*" >&2; exit 1; }
loaded() { launchctl list "$1" >/dev/null 2>&1; }
running() { pgrep -x "$1" >/dev/null 2>&1; }
need() { command -v "$1" >/dev/null || die "Missing $1. Run: $ROOT/wm.sh install"; }
reload_bar() {
    if running sketchybar; then
        sketchybar --reload "$HOME/.config/sketchybar/sketchybarrc"
    fi
}
wait_stopped() {
    local name=$1
    for _ in {1..30}; do
        running "$name" || return 0
        sleep 0.1
    done
    echo "$name is still running; refusing to start another window manager." >&2
    return 1
}
stop_trial() {
    if loaded "$SKHD_JOB"; then launchctl remove "$SKHD_JOB"; fi
    wait_stopped skhd || return 1
    if loaded "$YABAI_JOB"; then launchctl remove "$YABAI_JOB"; fi
    wait_stopped yabai
}
check_external_services() {
    local app label
    for app in yabai skhd; do
        for label in "com.asmvik.$app" "com.koekeishiya.$app" "homebrew.mxcl.$app"; do
            loaded "$label" && die "Stop the existing $label service before using wm.sh."
        done
        if running "$app" && ! loaded "local.dotfiles.$app"; then
            die "$app was started outside wm.sh. Stop it first."
        fi
    done
}
check_config() {
    local pkg
    for pkg in yabai skhd; do
        [ "$(readlink -f "$HOME/.config/$pkg/${pkg}rc" 2>/dev/null)" = \
          "$ROOT/$pkg/.config/$pkg/${pkg}rc" ] || die "Run $ROOT/wm.sh install to link this checkout's configs."
    done
}
save_pref() {
    local domain=$1 key=$2
    if [ ! -f "$STATE/$key.before" ]; then
        defaults read "$domain" "$key" > "$STATE/$key.before" 2>/dev/null || echo absent > "$STATE/$key.before"
    fi
}

case "${1:-help}" in
    help|--help|-h)
        cat <<'EOF'
Usage: ./wm.sh COMMAND
  install              Install yabai/skhd and link their dotfiles; start nothing
  doctor               Check dependencies, macOS preferences, and running apps
  prepare              Save/set native Spaces preferences; then log out and in
  yabai                Quit AeroSpace, start yabai + skhd, reload SketchyBar
  aerospace            Stop the trial, open AeroSpace, reload SketchyBar
  spaces               Label six existing desktops, preserving odd/even monitors
  reload               Reload yabai/skhd configuration and SketchyBar
  restore-preferences  Restore preferences saved by prepare; then log out and in
  status               Show running apps and trial jobs

SIP stays enabled. Trial jobs do not start at the next login. See YABAI.md.
EOF
        exit 0 ;;
esac
[ "$(uname -s)" = Darwin ] || die "This script requires macOS."
mkdir -p "$STATE"
umask 077

# Share the profile switcher's lock so it cannot reload a profile mid-switch.
exec 9>"${TMPDIR:-/tmp}/.display-mode-state.lock"
lockf -s -t 10 9 || die "Another desktop configuration change is running."

case "$1" in
    install)
        need brew
        brew bundle --file="$ROOT/Brewfile.yabai"
        mkdir -p "$HOME/.config"
        # A conflict aborts before Stow changes anything. Never adopt user files.
        stow --simulate --dir="$ROOT" --target="$HOME" yabai skhd
        stow --dir="$ROOT" --target="$HOME" yabai skhd
        echo "Installed and linked. Nothing started. Next: ./wm.sh doctor" ;;
    doctor|status)
        for app in AeroSpace yabai skhd sketchybar; do
            if running "$app"; then echo "$app: running"; else echo "$app: stopped"; fi
        done
        for app in yabai skhd; do
            if command -v "$app" >/dev/null; then "$app" --version; else echo "$app: not installed"; fi
        done
        echo "Displays have separate Spaces (0 = enabled): $(defaults read com.apple.spaces spans-displays 2>/dev/null || echo 'default')"
        echo "Automatically rearrange Spaces (0 = disabled): $(defaults read com.apple.dock mru-spaces 2>/dev/null || echo 'default')"
        echo "Accessibility permission is required for both yabai and skhd."
        echo "If skhd ignores keys, check whether your terminal has Secure Keyboard Entry enabled."
        if loaded "$YABAI_JOB"; then echo "yabai trial job: loaded"; fi
        if loaded "$SKHD_JOB"; then echo "skhd trial job: loaded"; fi
        if running yabai; then yabai -m query --spaces; fi ;;
    prepare)
        save_pref com.apple.spaces spans-displays
        save_pref com.apple.dock mru-spaces
        defaults write com.apple.spaces spans-displays -bool false
        defaults write com.apple.dock mru-spaces -bool false
        echo "Saved previous preferences in $STATE."
        echo "Log out and back in to enable separate Spaces, then run ./wm.sh yabai."
        echo "This script does not log you out or change SIP." ;;
    restore-preferences)
        running yabai && die "Switch to AeroSpace before restoring preferences."
        for key in spans-displays mru-spaces; do
            [ -f "$STATE/$key.before" ] || continue
            domain=com.apple.dock
            [ "$key" != spans-displays ] || domain=com.apple.spaces
            value=$(cat "$STATE/$key.before")
            if [ "$value" = absent ]; then
                defaults delete "$domain" "$key" 2>/dev/null || true
            else
                defaults write "$domain" "$key" -bool "$value"
            fi
            rm "$STATE/$key.before"
        done
        echo "Preferences restored. Log out and back in for the Spaces change." ;;
    yabai)
        need yabai; need skhd; need jq
        check_config
        check_external_services
        [ "$(defaults read com.apple.spaces spans-displays 2>/dev/null || echo 0)" != 1 ] || \
            die "Separate Spaces is disabled. Run ./wm.sh prepare, then log out and back in."
        [ "$(defaults read com.apple.dock mru-spaces 2>/dev/null || echo 1)" = 0 ] || \
            die "Disable automatic Space rearrangement with ./wm.sh prepare first."
        # Catch older installations missing SIP-enabled Space focus/movement.
        version=$(yabai --version | sed -nE 's/^[^0-9]*([0-9]+)\.([0-9]+)\.([0-9]+).*$/\1.\2.\3/p')
        [ -n "$version" ] || die "Could not determine the installed yabai version."
        printf '%s\n' "$version" | awk -F. '{ exit !(($1+0 > 7) || ($1+0 == 7 && ($2+0 > 1 || ($2+0 == 1 && $3+0 >= 25)))) }' || \
            die "yabai 7.1.25 or newer is required. Run ./wm.sh install to update."
        was_aerospace=false
        running AeroSpace && was_aerospace=true
        rollback() {
            code=$?
            trap - EXIT
            if [ "$code" -ne 0 ]; then
                echo "Trial startup failed. Check $STATE/*.log and Accessibility permissions." >&2
                if stop_trial; then
                    if $was_aerospace; then open -a AeroSpace; fi
                    reload_bar || true
                fi
            fi
            exit "$code"
        }
        trap rollback EXIT
        if $was_aerospace; then osascript -e 'tell application "AeroSpace" to quit'; fi
        wait_stopped AeroSpace
        if ! loaded "$YABAI_JOB"; then
            rm -f "$STATE/yabai-ready"
            launchctl submit -l "$YABAI_JOB" -o "$STATE/yabai.log" -e "$STATE/yabai.err.log" -- \
                /usr/bin/env "PATH=$PATH" "HOME=$HOME" "USER=$USER" "DOTFILES_YABAI_READY=$STATE/yabai-ready" \
                "$(command -v yabai)" -c "$HOME/.config/yabai/yabairc"
        fi
        ready=false
        for _ in {1..30}; do
            if [ -f "$STATE/yabai-ready" ] && yabai -m query --spaces >/dev/null 2>&1; then ready=true; break; fi
            sleep 0.2
        done
        $ready || die "yabai did not become ready. Grant Accessibility access and try again."
        if ! loaded "$SKHD_JOB"; then
            launchctl submit -l "$SKHD_JOB" -o "$STATE/skhd.log" -e "$STATE/skhd.err.log" -- \
                /usr/bin/env "PATH=$PATH" "HOME=$HOME" "USER=$USER" "SHELL=/bin/bash" \
                "$(command -v skhd)" -c "$HOME/.config/skhd/skhdrc"
        fi
        sleep 1
        running skhd || die "skhd exited. Grant Accessibility access and try again."
        reload_bar
        echo "yabai + skhd active for this login. Return with: $ROOT/wm.sh aerospace"
        echo "Create six desktops in Mission Control, then run ./wm.sh spaces."
        trap - EXIT ;;
    aerospace)
        check_external_services
        stop_trial
        open -a AeroSpace
        for _ in {1..30}; do
            running AeroSpace && break
            sleep 0.2
        done
        running AeroSpace || die "AeroSpace did not start."
        reload_bar
        echo "AeroSpace restored. Extra native desktops and window placement remain for you to tidy."
        # Release the lock before invoking the existing profile switcher.
        exec 9>&-
        "$ROOT/switch-display-mode.sh" ;;
    spaces|reload)
        loaded "$YABAI_JOB" || die "Start the trial with ./wm.sh yabai first."
        if [ "$1" = spaces ]; then
            "$HOME/.config/yabai/scripts/spaces.sh"
        else
            /bin/bash "$HOME/.config/yabai/yabairc"
            skhd --reload
        fi
        reload_bar ;;
    *) die "Unknown command: $1. Run ./wm.sh help" ;;
esac
