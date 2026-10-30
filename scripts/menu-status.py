#!/usr/bin/env python3
"""Read CodexBar usage, or open status items through Accessibility."""
import json
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
    # macOS 27.2 hides status items from Accessibility while the menu bar is
    # auto-hidden, so read CodexBar's data through its CLI instead.
    result = subprocess.run(
        ["/opt/homebrew/bin/codexbar", "usage", "--provider", "both", "--json", "--no-credits"],
        capture_output=True, text=True, timeout=45,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "codexbar usage failed")
    status = {}
    for entry in json.loads(result.stdout):
        usage = entry.get("usage") or {}
        windows = [window for key in ("primary", "secondary") if (window := usage.get(key))]
        if not windows:
            continue
        # Show the tightest window; name it ("W 4%") the way CodexBar's own
        # item does when it isn't the provider's only or primary window.
        shown = max(windows, key=lambda window: window["usedPercent"])
        named = len(windows) > 1 and shown is not windows[0]
        window = "W " if named and shown.get("windowMinutes") == 10080 else ""
        status[entry["provider"]] = window + str(round(shown["usedPercent"])) + "%"
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
