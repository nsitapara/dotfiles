#!/bin/bash
# Background poller: force an AeroSpace refresh every 0.5s so re-tiling after
# window creation/destruction never visibly stalls. Companion to
# aerospace-retile.sh (event-driven, instant when AeroSpace's events fire) —
# this covers the cases where AeroSpace's own async event pipeline is the thing
# that's delayed, which no event hook can beat.
# Workaround for https://github.com/nikitabobko/AeroSpace/issues/1615 — remove
# once the upstream reactive-refresh fix ships.
#
# Skips polling while a video app is frontmost: each refresh makes the focused
# app answer AX queries, which stutters playback. lsappinfo asks launchservicesd
# (not the app itself), so the check is free for the video app.

SKIP_FRONTMOST="com.nuvio.media.desktop"

LOCK="${TMPDIR:-/tmp}/aerospace-poll.pid"
/usr/bin/shlock -f "$LOCK" -p $$ || exit 0
trap 'rm -f "$LOCK"' EXIT

while true; do
    sleep 0.5
    # Stop when AeroSpace quits so we don't poll a dead server forever
    pgrep -xq AeroSpace || exit 0
    front=$(lsappinfo info -only bundleid "$(lsappinfo front)" 2>/dev/null)
    case "$front" in *"$SKIP_FRONTMOST"*) continue ;; esac
    /opt/homebrew/bin/aerospace list-windows --all >/dev/null 2>&1
done
