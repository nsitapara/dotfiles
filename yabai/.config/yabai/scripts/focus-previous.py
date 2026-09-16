#!/usr/bin/env python3
"""Remember the last two focused windows, including windows outside yabai's tree."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from wm_client import run


def command(*args):
    return run('yabai', '-m', *args, check=False, timeout=2)


def query(*args):
    result = command('query', *args)
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
    if not target.get('is-visible'):
        space = query('--spaces', '--space', target['space'])
        if not space:
            raise RuntimeError('Previous window workspace is unavailable')
        if not space.get('is-visible'):
            # Match Cmd+number: activate the Space explicitly, avoiding the
            # animated macOS switch caused by focusing an off-Space window.
            result = command('space', '--focus', target['space'])
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                space = query('--spaces', '--space', target['space'])
                if space and space.get('is-visible'):
                    break
                time.sleep(0.01)
            else:
                raise RuntimeError('Previous window workspace did not become visible')
    result = command('window', '--focus', target['id'])
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    remember(state, target)


def main(action):
    directory = Path.home() / '.local/state/dotfiles-wm'
    directory.mkdir(parents=True, exist_ok=True)
    # Signals must never wait for a toggle that is itself waiting on yabai.
    # The toggle saves its final target; intermediate focus events can be skipped.
    with (directory / 'focus-history.json').open('a+') as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
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
