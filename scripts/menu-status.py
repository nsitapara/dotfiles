#!/usr/bin/env python3
"""Read or open status items through Accessibility when window aliases are absent."""
import json
import re
import subprocess
import sys


def run_script(source):
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", source], capture_output=True, text=True, timeout=5
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def codexbar_status():
    titles = run_script('''
tell application "System Events"
    if not (exists process "CodexBar") then return ""
    tell process "CodexBar"
        set titles to name of every menu bar item of menu bar 2
        set AppleScript's text item delimiters to linefeed
        return titles as text
    end tell
end tell
''')
    status = {}
    for line in titles.splitlines():
        match = re.match(r"(Codex|Claude) icon, Usage (\d+)%", line)
        if match:
            status[match[1].lower()] = match[2] + "%"
    return status


def open_menu(provider):
    if provider == "amphetamine":
        source = '''tell application "System Events" to tell process "Amphetamine"
            ignoring application responses
                click menu bar item 1 of menu bar 2
            end ignoring
        end tell'''
    elif provider in ("codex", "claude"):
        title = provider.capitalize() + " icon,"
        source = f'''tell application "System Events" to tell process "CodexBar"
            repeat with item_ref in menu bar items of menu bar 2
                if name of item_ref starts with "{title}" then
                    ignoring application responses
                        click item_ref
                    end ignoring
                    return
                end if
            end repeat
            error "Provider menu is unavailable"
        end tell'''
    else:
        raise ValueError("Unknown provider")
    run_script(source)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["status"]:
            print(json.dumps(codexbar_status()))
        elif len(sys.argv) == 3 and sys.argv[1] == "open":
            open_menu(sys.argv[2])
        else:
            raise ValueError("Usage: menu-status.py status | open codex|claude|amphetamine")
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
