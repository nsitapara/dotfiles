#!/usr/bin/env python3
"""Activate the approved macOS 27 app, or restore the saved Homebrew symlink."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

APP = Path.home() / "Applications/Yabai macOS 27.app"
BINARY = APP / "Contents/MacOS/yabai"
STATE = Path.home() / ".local/state/dotfiles-wm/yabai-macos27-backup.json"
SERVICE = f"gui/{os.getuid()}/local.dotfiles.yabai"


def replace_link(link, target):
    temporary = link.with_name(f".yabai-link-{os.getpid()}")
    try:
        temporary.symlink_to(target)
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


def restart(link):
    subprocess.run(["launchctl", "kickstart", "-k", SERVICE], check=True, timeout=30)
    for _ in range(50):
        result = subprocess.run(
            [str(link), "-m", "query", "--spaces"], capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return
        time.sleep(0.1)
    raise RuntimeError("yabai did not respond; check Device Control and Data Access")


def main(action):
    prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    link = Path(prefix) / "bin/yabai"
    if not link.is_symlink():
        raise RuntimeError(f"Expected a Homebrew symlink at {link}")
    subprocess.run(["launchctl", "print", SERVICE], check=True, stdout=subprocess.DEVNULL)
    previous = os.readlink(link)
    if action == "activate":
        subprocess.run(["codesign", "--verify", "--strict", str(APP)], check=True)
        if not BINARY.is_file():
            raise RuntimeError("Build the macOS 27 app first")
        if previous != str(BINARY):
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"link": str(link), "target": previous}, indent=2) + "\n")
        target = str(BINARY)
    elif action == "rollback":
        if previous != str(BINARY):
            raise RuntimeError("The macOS 27 app is not selected; leaving the current link alone")
        saved = json.loads(STATE.read_text())
        if saved["link"] != str(link):
            raise RuntimeError("Backup belongs to a different Homebrew prefix")
        target = saved["target"]
        if not (link.parent / target).is_file():
            raise RuntimeError("The saved Homebrew binary no longer exists")
    else:
        raise ValueError("Usage: use-yabai-macos27.py activate|rollback")
    replace_link(link, target)
    try:
        restart(link)
    except (RuntimeError, subprocess.SubprocessError):
        replace_link(link, previous)
        restart(link)
        raise
    print(f"yabai service uses {link.resolve()}")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) == 2 else "")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
