#!/usr/bin/env python3
"""Remember the last two focused windows, including windows outside yabai's tree."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


def query(*args):
    result = subprocess.run(['yabai', '-m', 'query', *map(str, args)],
                            capture_output=True, text=True)
    return json.loads(result.stdout) if result.returncode == 0 else None


def identity(window):
    return {'id': window['id'], 'pid': window['pid']} if window else None


def remember(state, window):
    current = identity(window)
    if current and current != state.get('current'):
        state['previous'] = state.get('current')
        state['current'] = current


def focus_previous(state):
    remember(state, query('--windows', '--window'))
    previous = state.get('previous')
    if not previous:
        return
    target = query('--windows', '--window', previous['id'])
    # Do not focus a reused ID or revive a hidden/minimized application.
    if (identity(target) != previous or target.get('is-minimized')
            or target.get('is-hidden')):
        state['previous'] = None
        return
    result = subprocess.run(['yabai', '-m', 'window', '--focus', str(target['id'])],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    remember(state, target)


def main(action):
    directory = Path.home() / '.local/state/dotfiles-wm'
    directory.mkdir(parents=True, exist_ok=True)
    # One file lock serializes focus signals and shortcut presses. Signals query
    # current focus instead of trusting an event that may have arrived late.
    with (directory / 'focus-history.json').open('a+') as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        file.seek(0)
        try:
            state = json.load(file)
        except (ValueError, OSError):
            state = {}
        if action == 'reset':
            state = {}
        if action == 'toggle':
            focus_previous(state)
        else:
            remember(state, query('--windows', '--window'))
        file.seek(0)
        file.truncate()
        json.dump(state, file)


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    try:
        action = sys.argv[1] if len(sys.argv) == 2 else ''
        if action not in ('record', 'reset', 'toggle'):
            raise RuntimeError('Usage: focus-previous.py record|reset|toggle')
        main(action)
    except (RuntimeError, ValueError, OSError) as error:
        print('Previous window: ' + str(error), file=sys.stderr)
        sys.exit(1)
