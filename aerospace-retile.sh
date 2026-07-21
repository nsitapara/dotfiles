#!/bin/bash
# Event-driven half of the AeroSpace re-tile workaround (see also
# aerospace-poll.sh). Fires on focus change and forces quick refreshes so
# window creation re-tiles near-instantly. Workaround for the 0.20/0.21
# async rewrite: https://github.com/nikitabobko/AeroSpace/issues/1615
#
# Restart semantics: a new invocation kills any still-running loop and starts a
# fresh poll window — at most one loop alive, and every event gets full
# coverage. Remove this script once the upstream reactive-refresh fix ships.

LOCK="${TMPDIR:-/tmp}/aerospace-retile.pid"
[ -f "$LOCK" ] && kill "$(cat "$LOCK")" 2>/dev/null
echo $$ > "$LOCK"

# Cover the first 0.5s only — beyond that the 0.5s poller is the backstop.
for d in 0 0.2 0.3; do
    sleep "$d"
    /opt/homebrew/bin/aerospace list-windows --all >/dev/null 2>&1
done

[ "$(cat "$LOCK" 2>/dev/null)" = "$$" ] && rm -f "$LOCK"
