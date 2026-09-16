#!/bin/bash
# Install and switch window managers. wm-startup.py manages the login default.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"
STATE="${DOTFILES_WM_STATE_DIR:-$HOME/.local/state/dotfiles-wm}"
YABAI_JOB=local.dotfiles.yabai
SKHD_JOB=local.dotfiles.skhd
RIFT_JOB=local.dotfiles.rift

die() { echo "$*" >&2; exit 1; }
loaded() { launchctl list "$1" >/dev/null 2>&1; }
running() { pgrep -x "$1" >/dev/null 2>&1; }
need() { command -v "$1" >/dev/null || die "Missing $1. Run: $ROOT/wm.sh install"; }
probe_command() {
    /usr/bin/python3 -c 'import subprocess,sys
try:
    sys.exit(subprocess.run(sys.argv[1:], timeout=1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode)
except subprocess.TimeoutExpired:
    sys.exit(1)' "$@"
}
skhd_log_offset() {
    if [ -f "$STATE/skhd.err.log" ]; then wc -c < "$STATE/skhd.err.log"; else echo 0; fi
}
check_skhd() {
    local offset=$1 errors
    sleep 1
    errors=$(tail -c "+$((offset + 1))" "$STATE/skhd.err.log" 2>/dev/null || true)
    running skhd || die "skhd exited: ${errors:-no output}. Check Accessibility access."
    # skhd remains alive when parsing fails, so process presence is insufficient.
    if printf '%s\n' "$errors" | grep -Eq '^#[0-9]+:[0-9]+|could not open config'; then
        printf '%s\n' "$errors" >&2
        die "skhd could not load its shortcuts. Fix skhdrc before retrying."
    fi
}
wait_secure_input() {
    # Right after login, securityagent still holds Secure Keyboard Entry for a
    # moment. skhd aborts at startup while it is held, so wait for the release.
    local holder
    for _ in {1..150}; do
        holder=$(ioreg -l -w 0 | grep -o 'kCGSSessionSecureInputPID[^,}]*' || true)
        [ -n "$holder" ] || return 0
        sleep 0.2
    done
    die "Secure Keyboard Entry is enabled ($holder). Disable it in that app and retry."
}
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
# Manager lifecycle operations share this script's descriptor lock.
source "$ROOT/scripts/wm-lifecycle.sh"

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
  install [MANAGER]    Install/link yabai (default), aerospace, or rift; start nothing
  use MANAGER          Switch now and at login: rift, yabai, or aerospace
  use MANAGER --temporary  Switch only for the current login
  quit                 Stop running managers and shortcuts; keep apps and login default
  rift                 Switch to Rift for this login
  doctor               Check dependencies, macOS preferences, and running apps
  prepare              Save/set native Spaces preferences; then log out and in
  yabai                Quit AeroSpace, start yabai + skhd, reload SketchyBar
  aerospace            Switch to AeroSpace and reload SketchyBar
  default MANAGER      Switch now and at login: yabai, aerospace, or rift
  default status       Show the saved login default
  default install      Install/repair the desktop service with the saved choice
  default off          Remove desktop service; keep current manager running
  spaces               Create missing desktops, remove empty spares, label monitors
  profile [NAME]       Show or pin the display profile: auto, docked, single, laptop
  reload               Reload yabai/skhd configuration and SketchyBar
  restore-preferences  Restore preferences saved by prepare; then log out and in
  status               Show running apps and owned jobs

SIP stays enabled. See RIFT.md for shared switching and YABAI.md for the baseline.
EOF
        exit 0 ;;
esac
[ "$(uname -s)" = Darwin ] || die "This script requires macOS."
if [ "$1" = use ]; then
    case "${2:-}" in yabai|aerospace|rift) ;; *) die "Use: ./wm.sh use rift|yabai|aerospace [--temporary]" ;; esac
    case "$#:${3:-}" in
        2:) exec /usr/bin/python3 "$ROOT/wm-startup.py" "$2" ;;
        3:--temporary) set -- "$2" ;;
        *) die "Use: ./wm.sh use rift|yabai|aerospace [--temporary]" ;;
    esac
fi
if [ "$1" = default ]; then
    exec /usr/bin/python3 "$ROOT/wm-startup.py" "${2:-status}"
fi
mkdir -p "$STATE"
umask 077

# Bar status reads must not wait on the lock while a switch is waiting for the bar.
if [ "$1" = current ]; then active_manager; exit 0; fi
if [ "$1" = profile ] && [ "$#" -eq 1 ]; then
    pin="$STATE/display-profile.pin"
    applied=$(jq -r '.[0].profile // "unknown"' "$STATE/display-layout.json" 2>/dev/null || echo unknown)
    echo "$(cat "$pin" 2>/dev/null || echo auto) $applied $(active_manager)"
    exit 0
fi

# Share the profile switcher's lock so it cannot reload a profile mid-switch.
if [ "${DOTFILES_WM_LOCKED:-0}" != 1 ]; then
    exec 9>"${TMPDIR:-/tmp}/.display-mode-state.lock"
    lockf -s -t 10 9 || die "Another desktop configuration change is running."
fi

case "$1" in
    quit)
        export DOTFILES_WM_LOCKED=1
        exec /usr/bin/python3 "$ROOT/scripts/wm-quit.py" ;;
    install)
        case "${2:-yabai}" in
            rift)
                /usr/bin/python3 "$ROOT/scripts/install-rift.py"
                need stow; need skhd; need jq
                stow --simulate --dir="$ROOT" --target="$HOME" rift skhd
                stow --dir="$ROOT" --target="$HOME" rift skhd
                echo "Rift installed. Grant Accessibility access, then run ./wm.sh use rift."
                exit 0 ;;
            aerospace)
                need brew
                brew install --cask nikitabobko/tap/aerospace
                echo "AeroSpace installed. Run ./wm.sh use aerospace to apply the display profile."
                exit 0 ;;
            yabai) ;;
            *) die "Unknown manager: $2" ;;
        esac
        need brew
        # Recent Homebrew versions require trust before loading third-party
        # formulae. Scope it to the two packages this installer requests.
        if brew help trust >/dev/null 2>&1; then
            brew trust --formula asmvik/formulae/yabai asmvik/formulae/skhd
        fi
        brew bundle --file="$ROOT/Brewfile.yabai"
        mkdir -p "$HOME/.config"
        # A conflict aborts before Stow changes anything. Never adopt user files.
        stow --simulate --dir="$ROOT" --target="$HOME" yabai skhd
        stow --dir="$ROOT" --target="$HOME" yabai skhd
        "$ROOT/yabai/.config/yabai/scripts/build-spaces-helper.sh"
        echo "Installed and linked. Nothing started. Next: ./wm.sh doctor" ;;
    doctor|status)
        for app in AeroSpace yabai rift skhd sketchybar; do
            if running "$app"; then echo "$app: running"; else echo "$app: stopped"; fi
        done
        for app in yabai rift skhd; do
            if command -v "$app" >/dev/null; then "$app" --version; else echo "$app: not installed"; fi
        done
        echo "Displays have separate Spaces (0 = enabled): $(defaults read com.apple.spaces spans-displays 2>/dev/null || echo 'default')"
        echo "Automatically rearrange Spaces (0 = disabled): $(defaults read com.apple.dock mru-spaces 2>/dev/null || echo 'default')"
        echo "Active manager: $(active_manager)"
        /usr/bin/python3 "$ROOT/wm-startup.py" status
        echo "Accessibility permission is required for the selected manager and skhd."
        if loaded "$RIFT_JOB"; then rift-cli query displays; fi
        echo "If skhd ignores keys, check whether your terminal has Secure Keyboard Entry enabled."
        if loaded "$YABAI_JOB"; then echo "yabai owned job: loaded"; fi
        if loaded "$SKHD_JOB"; then echo "skhd owned job: loaded"; fi
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
        { running yabai || running rift; } && die "Switch to AeroSpace before restoring preferences."
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
    _stop) stop_manager "$2" ;;
    current) active_manager ;;
    yabai|aerospace|rift)
        switch_manager "$1" ;;
    profile)
        pin="$STATE/display-profile.pin"
        case "${2:-}" in
            "")
                applied=$(jq -r '.[0].profile // "unknown"' "$STATE/display-layout.json" 2>/dev/null || echo unknown)
                echo "$(cat "$pin" 2>/dev/null || echo auto) $applied $(active_manager)"
                exit 0 ;;
            auto) rm -f "$pin" ;;
            docked|single|laptop) printf '%s\n' "$2" > "$pin" ;;
            *) die "Unknown profile: $2. Use auto, docked, single, or laptop." ;;
        esac
        rm -f "$STATE/display-profile.signature"
        exec 9>&-
        exec "$ROOT/switch-display-mode.sh" ;;
    spaces|reload)
        if running rift; then
            if [ "$1" = reload ]; then rift-cli execute config reload; skhd --reload; fi
            DOTFILES_WM_LOCKED=1 /usr/bin/python3 "$ROOT/wm_rift.py" profile
            exit 0
        elif running AeroSpace; then
            aerospace reload-config
            exec 9>&-
            exec "$ROOT/switch-display-mode.sh"
        fi
        loaded "$YABAI_JOB" || die "Start the trial with ./wm.sh yabai first."
        if [ "$1" = spaces ]; then
            "$ROOT/yabai/.config/yabai/scripts/ensure-spaces.sh"
        else
            /bin/bash "$HOME/.config/yabai/yabairc"
            "$ROOT/yabai/.config/yabai/scripts/ensure-spaces.sh"
            skhd_offset=$(skhd_log_offset)
            skhd --reload
            check_skhd "$skhd_offset"
        fi
        reload_bar
        # yabairc resets global padding; reapply per-screen padding after reload.
        rm -f "$STATE/display-profile.signature"
        exec 9>&-
        "$ROOT/switch-display-mode.sh" ;;
    *) die "Unknown command: $1. Run ./wm.sh help" ;;
esac
