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
LABEL = "local.dotfiles.desktop"
LEGACY_LABELS = ("local.dotfiles.wm-login", "com.user.display-mode-switcher")


def run(*args):
    subprocess.run(args, check=True)


def loaded(service):
    return subprocess.run(
        ["launchctl", "print", service], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def saved_manager():
    for label in (LABEL, *LEGACY_LABELS):
        agent = HOME / "Library/LaunchAgents" / (label + ".plist")
        if agent.exists():
            with agent.open("rb") as stream:
                args = plistlib.load(stream).get("ProgramArguments", [])
            if args and args[-1] in ("yabai", "aerospace"):
                return args[-1]
    return None


def retire_legacy(domain, state):
    for label in LEGACY_LABELS:
        service = domain + "/" + label
        if loaded(service):
            run("launchctl", "bootout", service)
        agent = HOME / "Library/LaunchAgents" / (label + ".plist")
        if agent.exists():
            backups = state / "disabled-launch-agents"
            backups.mkdir(parents=True, exist_ok=True)
            archive = Path(tempfile.mkdtemp(prefix="desktop-migration-", dir=backups))
            agent.rename(archive / agent.name)


def configure(manager):
    agent = HOME / "Library/LaunchAgents" / (LABEL + ".plist")
    domain = "gui/" + str(os.getuid())
    service = domain + "/" + LABEL
    state = Path(os.environ.get("DOTFILES_WM_STATE_DIR", HOME / ".local/state/dotfiles-wm"))

    if manager == "status":
        saved = saved_manager()
        if saved:
            print("Login window manager: " + saved)
        else:
            print("Desktop service is not installed.")
        return
    if manager == "install":
        manager = saved_manager() or "yabai"

    is_loaded = loaded(service)
    if manager == "off":
        if is_loaded:
            run("launchctl", "bootout", service)
        agent.unlink(missing_ok=True)
        retire_legacy(domain, state)
        print("Desktop service removed. The current window manager is still running.")
        return

    # Refuse to save a default that cannot start. wm.sh owns mutual exclusion,
    # config/permission checks, and rollback to the previously running AeroSpace.
    run("/bin/bash", str(ROOT / "wm.sh"), manager)
    state.mkdir(parents=True, exist_ok=True)
    config = {
        "Label": LABEL,
        "ProgramArguments": [str(ROOT / "switch-display-mode.sh"), "--service", manager],
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
    # The script owns the interval. No StartInterval or second polling job.
    # No KeepAlive: a service crash must not undo a manual manager switch.
    data = plistlib.dumps(config)
    if not agent.exists() or agent.read_bytes() != data:
        agent.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=agent.parent, delete=False) as stream:
            stream.write(data)
            temporary = Path(stream.name)
        temporary.chmod(0o644)
        temporary.replace(agent)
        if is_loaded:
            run("launchctl", "bootout", service)
            is_loaded = False
    run("launchctl", "enable", service)
    if not is_loaded:
        # RunAtLoad also invokes the switcher once now. Repeated starts are safe.
        run("launchctl", "bootstrap", domain, str(agent))
    else:
        # Without -k this starts an exited service and leaves a running one alone.
        run("launchctl", "kickstart", service)
    # Retire both old jobs only after the replacement has been registered.
    retire_legacy(domain, state)
    print(manager + " is the default window manager now and at login.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manager", choices=("yabai", "aerospace", "install", "status", "off"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This script requires macOS.")
    configure(args.manager)


if __name__ == "__main__":
    main()
