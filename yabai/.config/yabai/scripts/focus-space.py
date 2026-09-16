#!/usr/bin/env python3
"""Switch native Spaces and recover window focus if macOS leaves Finder active."""
import json
import fcntl
from contextlib import contextmanager
from pathlib import Path
import os
import sys
import time


# Resolve the checkout when launched through the stowed config directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from wm_client import run


def command(*args):
    return run('yabai', '-m', *args, check=False, timeout=2)


def query(*args):
    result = command('query', *args)
    return json.loads(result.stdout) if result.returncode == 0 else None


def visible(window, space):
    return (window and window.get('space') == space['index']
            and window.get('is-visible', False)
            and not window.get('is-minimized', False)
            and not window.get('is-hidden', False))


def restore(space):
    """One worker drains the latest request; event handlers never wait on repairs."""
    if not space or space.get('is-native-fullscreen'):
        return
    directory = Path.home() / '.local/state/dotfiles-wm'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'focus-repair.request').open('a+') as request, \
            (directory / 'focus-repair.lock').open('a+') as worker:
        with locked(request):
            request.seek(0)
            request.truncate()
            json.dump(space, request)
            request.flush()
            try:
                fcntl.flock(worker, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # The worker will pick up this request after its current repair.
        failure = None
        while True:
            with locked(request):
                request.seek(0)
                pending = request.read()
                if not pending:
                    # Release ownership under the request lock so a new request
                    # cannot be stranded behind a worker that is about to exit.
                    fcntl.flock(worker, fcntl.LOCK_UN)
                    if failure:
                        raise failure
                    return
                request.seek(0)
                request.truncate()
                request.flush()
            try:
                restore_window(json.loads(pending))
                failure = None
            except (RuntimeError, ValueError, KeyError, OSError) as error:
                failure = error  # Drain newer requests even if an older repair failed.


@contextmanager
def locked(file):
    fcntl.flock(file, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(file, fcntl.LOCK_UN)


def restore_window(space):
    if not space or space.get('is-native-fullscreen'):
        return
    # Space/display events can arrive before macOS finishes activating the Space.
    for attempt in range(9):
        if attempt:
            time.sleep(0.08)
        current = query('--spaces', '--space')
        if not current or current['id'] != space['id']:
            return  # The user already switched somewhere else.
        focused = query('--windows', '--window')
        if visible(focused, current) and focused.get('has-focus'):
            return
        if attempt == 0:
            continue  # Fast path checks focus; repair still waits for activation.
        windows = query('--windows', '--space', current['index'])
        if windows is None:
            return
        candidates = [w for w in windows if visible(w, current)]
        if not candidates:
            if (not windows and not current.get('windows')) or (windows and all(
                    w.get('is-hidden') or w.get('is-minimized') for w in windows)):
                return  # Activation grace elapsed; nothing here can receive focus.
            continue  # A non-hidden window may still be activating.
        # The native Space's window order prefers its frontmost eligible window.
        rank = {id: i for i, id in enumerate(current.get('windows', []))}
        target = min(candidates, key=lambda w: rank.get(w['id'], len(rank)))
        latest = query('--spaces', '--space')
        if not latest or latest['id'] != space['id']:
            return
        focused = query('--windows', '--window')
        if visible(focused, latest) and focused.get('has-focus'):
            return
        command('window', '--focus', target['id'])


def switch(selector):
    target = query('--spaces', '--space', selector)
    if not target:
        raise RuntimeError('Workspace is not available: ' + selector)
    result = command('space', '--focus', target['index'])
    if result.returncode:
        current = query('--spaces', '--space')
        if not current or current['id'] != target['id']:
            raise RuntimeError(result.stderr.strip())
        # Focusing the already-active Space fails in yabai, but can still need repair.
    restore(target)


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    try:
        if len(sys.argv) == 2 and sys.argv[1] == '--restore':
            restore(query('--spaces', '--space'))
        elif len(sys.argv) == 2:
            switch(sys.argv[1])
        else:
            raise RuntimeError('Usage: focus-space.py SPACE|--restore')
    except (RuntimeError, ValueError, KeyError, OSError) as error:
        print('Workspace focus: ' + str(error), file=sys.stderr)
        sys.exit(1)
