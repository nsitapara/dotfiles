#!/usr/bin/env python3
"""Workspace switching from SketchyBar without moving the mouse pointer."""
import fcntl
import importlib.util
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path.home() / '.local/state/dotfiles-wm'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def yabai_switch(workspace):
    direction = module('wm_direction', ROOT / 'wm-direction.py')
    focus = module('focus_space', ROOT / 'yabai/.config/yabai/scripts/focus-space.py')
    # Keep the existing focus repair, using bounded native socket requests.
    focus.command = lambda *args: direction.run('yabai', '-m', *args, check=False)
    previous = direction.run('yabai', '-m', 'config', 'mouse_follows_focus').stdout.strip()
    if previous not in ('on', 'off'):
        raise RuntimeError('Could not read mouse-follows-focus setting')
    try:
        if previous == 'on':
            direction.run('yabai', '-m', 'config', 'mouse_follows_focus', 'off')
        focus.switch(workspace)
    finally:
        if previous == 'on':
            direction.run('yabai', '-m', 'config', 'mouse_follows_focus', previous)


def aerospace_switch(workspace, close_others=False):
    marker = STATE / 'bar-mouse-suppressed'
    # The callback guard checks both the owner PID and deadline. A crashed
    # click helper cannot permanently suppress keyboard mouse-follow behavior.
    marker.write_text(f'{os.getpid()} {time.time() + 4}\n')
    try:
        subprocess.run(['aerospace', 'workspace', workspace], check=True, timeout=3)
        if close_others:
            subprocess.run(['aerospace', 'close-all-windows-but-current'], check=True, timeout=3)
        # AeroSpace runs exec-and-forget focus callbacks asynchronously. Keep
        # the guard through their dispatch; the workspace is already displayed.
        time.sleep(0.15)
    finally:
        marker.unlink(missing_ok=True)


def main(manager, workspace, close_others=False):
    if manager not in ('yabai', 'aerospace') or not workspace.isdecimal():
        raise RuntimeError('Expected a manager and numeric workspace')
    if close_others and manager != 'aerospace':
        raise RuntimeError('Close-other-windows is only bound in AeroSpace')
    STATE.mkdir(parents=True, exist_ok=True)
    # Only bar clicks take this lock. Keyboard shortcuts and focus callbacks
    # never wait for it. Serializing clicks prevents restoring an old setting.
    with (STATE / ('bar-switch-' + manager + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if manager == 'yabai':
            yabai_switch(workspace)
        else:
            aerospace_switch(workspace, close_others)


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    # Let finally blocks restore the mouse setting on ordinary termination.
    signal.signal(signal.SIGTERM, lambda number, frame: sys.exit(128 + number))
    try:
        if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != '--close-others'):
            raise RuntimeError('Usage: wm-bar-workspace.py MANAGER WORKSPACE [--close-others]')
        main(sys.argv[1], sys.argv[2], len(sys.argv) == 4)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('Bar workspace: ' + str(error), file=sys.stderr)
        sys.exit(1)
