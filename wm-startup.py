#!/usr/bin/env python3
"""Choose a window manager now and at login, using wm.sh for safe switching."""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
LABEL = "local.dotfiles.wm-login"


def run(*args):
    subprocess.run(args, check=True)


def configure(manager):
    agent = HOME / "Library/LaunchAgents" / (LABEL + ".plist")
    domain = "gui/" + str(os.getuid())
    service = domain + "/" + LABEL

    if manager == "status":
        if agent.exists():
            with agent.open("rb") as stream:
                config = plistlib.load(stream)
            print("Login window manager: " + config["ProgramArguments"][-1])
        else:
            print("Window manager login launcher is not installed.")
        return

    loaded = subprocess.run(
        ["launchctl", "print", service], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if manager == "off":
        if loaded:
            run("launchctl", "bootout", service)
        agent.unlink(missing_ok=True)
        print("Login launcher removed. The current window manager is still running.")
        return

    # Refuse to save a default that cannot start. wm.sh owns mutual exclusion,
    # config/permission checks, and rollback to the previously running AeroSpace.
    run("/bin/bash", str(ROOT / "wm.sh"), manager)
    state = Path(os.environ.get("DOTFILES_WM_STATE_DIR", HOME / ".local/state/dotfiles-wm"))
    state.mkdir(parents=True, exist_ok=True)
    config = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(ROOT / "wm.sh"), manager],
        "RunAtLoad": True,
        "LimitLoadToSessionType": "Aqua",
        "EnvironmentVariables": {
            "HOME": str(HOME),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "DOTFILES_WM_STATE_DIR": str(state),
        },
        "StandardOutPath": str(state / "login.log"),
        "StandardErrorPath": str(state / "login.err.log"),
    }
    # No KeepAlive: switching manually must not make launchd restart the old WM.
    data = plistlib.dumps(config)
    if not agent.exists() or agent.read_bytes() != data:
        agent.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=agent.parent, delete=False) as stream:
            stream.write(data)
            temporary = Path(stream.name)
        temporary.chmod(0o644)
        temporary.replace(agent)
        if loaded:
            run("launchctl", "bootout", service)
            loaded = False
    run("launchctl", "enable", service)
    if not loaded:
        # RunAtLoad also invokes the switcher once now. Repeated starts are safe.
        run("launchctl", "bootstrap", domain, str(agent))
    print(manager + " is the default window manager now and at login.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manager", choices=("yabai", "aerospace", "status", "off"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This script requires macOS.")
    configure(args.manager)


if __name__ == "__main__":
    main()
