#!/usr/bin/env python3
"""Open native menu bar status items through Accessibility."""
import subprocess
import sys


def run_script(source):
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", source], capture_output=True, text=True, timeout=5
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def open_menu(provider):
    if provider == "amphetamine":
        source = '''tell application "System Events" to tell process "Amphetamine"
            ignoring application responses
                click menu bar item 1 of menu bar 2
            end ignoring
        end tell'''
    else:
        raise ValueError("Unknown provider")
    run_script(source)


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "open":
            open_menu(sys.argv[2])
        else:
            raise ValueError("Usage: menu-status.py open amphetamine")
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
