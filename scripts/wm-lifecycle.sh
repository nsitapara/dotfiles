# Sourced by wm.sh. All mutations run under its desktop lock.
active_manager() {
    local name found=none
    for name in yabai AeroSpace; do
        if running "$name"; then
            [ "$found" = none ] || die "Multiple window managers are running. Stop the extra instance first."
            found=$name
        fi
    done
    [ "$found" != AeroSpace ] || found=aerospace
    echo "$found"
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
preflight() {
    local manager=$1 version
    check_external_services
    case "$manager" in
        aerospace) need aerospace ;;
        yabai)
            need "$manager"; need skhd; need jq
            [ "$(defaults read com.apple.spaces spans-displays 2>/dev/null || echo 0)" != 1 ] || \
                die "Separate Spaces is disabled. Run ./wm.sh prepare, then log out and back in."
            wait_secure_input
            check_config
            [ "$(defaults read com.apple.dock mru-spaces 2>/dev/null || echo 1)" = 0 ] || \
                die "Disable automatic Space rearrangement with ./wm.sh prepare first."
            version=$(yabai --version | sed -nE 's/^[^0-9]*([0-9]+)\.([0-9]+)\.([0-9]+).*$/\1.\2.\3/p')
            [ -n "$version" ] || die "Could not determine the installed yabai version."
            printf '%s\n' "$version" | awk -F. '{ exit !(($1+0 > 7) || ($1+0 == 7 && ($2+0 > 1 || ($2+0 == 1 && $3+0 >= 25)))) }' || \
                die "yabai 7.1.25 or newer is required." ;;
    esac
}
stop_manager() {
    local manager=$1
    if loaded "$SKHD_JOB"; then launchctl remove "$SKHD_JOB"; fi
    wait_stopped skhd
    case "$manager" in
        yabai)
            if loaded "$YABAI_JOB"; then launchctl remove "$YABAI_JOB"; fi
            wait_stopped yabai ;;
        aerospace)
            if running AeroSpace; then osascript -e 'tell application "AeroSpace" to quit'; fi
            wait_stopped AeroSpace ;;
    esac
}
start_manager() {
    local manager=$1 ready=false skhd_config offset
    local developer_env=()
    if [ -n "${DEVELOPER_DIR:-}" ]; then developer_env=("DEVELOPER_DIR=$DEVELOPER_DIR"); fi
    case "$manager" in
        yabai)
            rm -f "$STATE/yabai-ready"
            launchctl submit -l "$YABAI_JOB" -o "$STATE/yabai.log" -e "$STATE/yabai.err.log" -- \
                /usr/bin/env ${developer_env[@]+"${developer_env[@]}"} "PATH=$PATH" "HOME=$HOME" "USER=$USER" "DOTFILES_YABAI_READY=$STATE/yabai-ready" \
                "$(command -v yabai)" -c "$HOME/.config/yabai/yabairc"
            # Right after login the displays can still be re-probing, which makes
            # the space query fail for a while; give the daemon up to 60 s.
            for _ in {1..300}; do
                if [ -f "$STATE/yabai-ready" ] && probe_command yabai -m query --spaces; then ready=true; break; fi
                sleep 0.2
            done
            $ready || die "yabai did not become ready. Check Accessibility access."
            skhd_config="$HOME/.config/skhd/skhdrc" ;;
        aerospace)
            open -a AeroSpace
            for _ in {1..30}; do
                if probe_command aerospace list-monitors; then ready=true; break; fi
                sleep 0.2
            done
            $ready || die "AeroSpace did not become ready."
            aerospace enable on
            return ;;
    esac
    start_shortcuts "$skhd_config"
}
start_shortcuts() {
    local skhd_config=$1 offset
    local developer_env=()
    if [ -n "${DEVELOPER_DIR:-}" ]; then developer_env=("DEVELOPER_DIR=$DEVELOPER_DIR"); fi
    offset=$(skhd_log_offset)
    launchctl submit -l "$SKHD_JOB" -o "$STATE/skhd.log" -e "$STATE/skhd.err.log" -- \
        /usr/bin/env ${developer_env[@]+"${developer_env[@]}"} "PATH=$PATH" "HOME=$HOME" "USER=$USER" "SHELL=/bin/bash" \
        "$(command -v skhd)" -c "$skhd_config"
    check_skhd "$offset"
}
apply_manager() {
    case "$1" in
        yabai)
            if ! "$ROOT/yabai/.config/yabai/scripts/ensure-spaces.sh"; then
                echo "Desktop creation unavailable; labelling existing desktops." >&2
                "$ROOT/yabai/.config/yabai/scripts/spaces.sh"
            fi
            DOTFILES_WM_LOCKED=1 "$ROOT/yabai/.config/yabai/scripts/display-profile.sh" --force ;;
        aerospace)
            # Always reload on manager changes, even if the display profile is unchanged.
            DOTFILES_WM_LOCKED=1 "$ROOT/switch-display-mode.sh"
            reload_bar ;;
    esac
}
switch_manager() {
    target_manager=$1
    previous_manager=$(active_manager)
    preflight "$target_manager"
    if [ "$previous_manager" = "$target_manager" ]; then
        case "$target_manager" in
            yabai) probe_command yabai -m query --spaces ;;
            aerospace) probe_command aerospace list-monitors ;;
        esac
        if [ "$target_manager" != aerospace ] && ! running skhd; then
            if loaded "$SKHD_JOB"; then launchctl remove "$SKHD_JOB"; fi
            start_shortcuts "$HOME/.config/skhd/skhdrc"
        fi
        /usr/bin/python3 "$ROOT/scripts/wm-bar.py" "$target_manager"
        echo "$target_manager is already active. Use ./wm.sh reload to reapply configuration."
        return
    fi
    export DOTFILES_WM_LOCKED=1
    switch_started=false
    recover_switch() {
        local code=$?
        trap - EXIT
        if [ "$code" -ne 0 ] && $switch_started; then
            echo "Switch to $target_manager failed; restoring $previous_manager. See $STATE/*.log." >&2
            # Run cleanup in a new shell: failures must stop cleanup, not inherit
            # the relaxed errexit behavior of an if/! function call.
            if [ "$(active_manager)" = "$previous_manager" ] && [ "$previous_manager" != none ]; then
                DOTFILES_WM_RECOVER=1 /bin/bash "$ROOT/wm.sh" "$previous_manager" && \
                    /usr/bin/python3 "$ROOT/scripts/wm-session.py" restore "$previous_manager" || \
                    echo "Recovery needs attention. Run ./wm.sh doctor." >&2
            elif DOTFILES_WM_RECOVER=1 /bin/bash "$ROOT/wm.sh" _stop "$target_manager"; then
                if [ "$previous_manager" != none ]; then
                    DOTFILES_WM_RECOVER=1 /bin/bash "$ROOT/wm.sh" "$previous_manager" || \
                        echo "Recovery failed. Run ./wm.sh doctor; no second manager was started." >&2
                else
                    reload_bar || true
                fi
            fi
        fi
        exit "$code"
    }
    trap recover_switch EXIT
    if [ "$previous_manager" != none ] && [ "${DOTFILES_WM_RECOVER:-0}" != 1 ]; then
        /usr/bin/python3 "$ROOT/scripts/wm-session.py" capture "$previous_manager"
    fi
    switch_started=true
    if [ "$previous_manager" != none ] && [ "${DOTFILES_WM_RECOVER:-0}" != 1 ]; then
        /usr/bin/python3 "$ROOT/scripts/wm-session.py" prepare "$previous_manager" "$target_manager"
    fi
    stop_manager "$previous_manager"
    start_manager "$target_manager"
    apply_manager "$target_manager"
    if [ "${DOTFILES_WM_SKIP_RESTORE:-0}" != 1 ]; then
        /usr/bin/python3 "$ROOT/scripts/wm-session.py" restore "$target_manager"
    fi
    # A successful process switch is not enough: old bar callbacks can still
    # send clicks to the wrong manager.
    /usr/bin/python3 "$ROOT/scripts/wm-bar.py" "$target_manager"
    printf '%s\n' "$target_manager" > "$STATE/active-manager"
    trap - EXIT
    echo "$target_manager active."
}
