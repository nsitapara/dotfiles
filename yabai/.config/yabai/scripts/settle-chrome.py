#!/usr/bin/env python3
"""Reapply existing tiles if a detached Chrome tab leaves overlapping windows."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from wm_client import run


def query(*args):
    result = run('yabai', '-m', 'query', *args, check=False, timeout=2)
    return json.loads(result.stdout) if result.returncode == 0 else None


def mouse_button_reader():
    # Read physical button state, not yabai's cached "is-grabbed" flag. During
    # tab detachment the grabbed window can still be the original Chrome window.
    core = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    button_state = core.CGEventSourceButtonState
    button_state.argtypes = [ctypes.c_int32, ctypes.c_uint32]
    button_state.restype = ctypes.c_bool
    return lambda: any(button_state(0, button) for button in (0, 1, 2))


def tiled(window):
    return (window.get('is-visible') and window.get('subrole') == 'AXStandardWindow'
            and window.get('split-type') in ('horizontal', 'vertical')
            and not any(window.get(key) for key in (
                'is-floating', 'is-minimized', 'is-hidden', 'is-native-fullscreen',
                'has-parent-zoom', 'has-fullscreen-zoom', 'stack-index')))


def overlaps(a, b):
    a, b = a['frame'], b['frame']
    return all(min(a[pos] + a[size], b[pos] + b[size]) - max(a[pos], b[pos]) > 2
               for pos, size in (('x', 'w'), ('y', 'h')))


def repair(window_id, identity, button_down):
    window = query('--windows', '--window', window_id)
    if (not window or (window['pid'], window['space']) != identity
            or window.get('app') != 'Google Chrome' or not tiled(window)):
        return False
    space = query('--spaces', '--space', window['space'])
    if not space or space['type'] != 'bsp' or not space.get('is-visible'):
        return False
    windows = query('--windows', '--space', window['space'])
    if not windows or any(w.get('has-parent-zoom') or w.get('has-fullscreen-zoom') for w in windows):
        return False
    tiles = [w for w in windows if tiled(w)]
    # A valid layout (including deliberately unequal splits) needs no change.
    if any(overlaps(a, b) for i, a in enumerate(tiles) for b in tiles[i + 1:]):
        if button_down():
            return False
        # A zero padding delta runs view_update/view_flush without changing the
        # BSP tree, split ratios, padding, focus, or floating windows. --layout
        # rebuilds the tree and --balance discards the user's chosen ratios.
        run('yabai', '-m', 'space', window['space'], '--padding', 'rel:0:0:0:0', timeout=2)
    return True


def settle(window_id, button_down):
    window = query('--windows', '--window', window_id)
    if not window or window.get('app') != 'Google Chrome':
        return
    identity = window['pid'], window['space']
    deadline = time.monotonic() + 30
    released_at = None
    checks = 0
    while time.monotonic() < deadline:
        if button_down():
            released_at = None
        elif released_at is None:
            released_at = time.monotonic()
        elif time.monotonic() - released_at >= 0.35:
            if not repair(window_id, identity, button_down):
                return
            checks += 1
            if checks == 2:
                return
            # Check once more for a late Chrome resize. There is no permanent
            # polling process and no handler for ordinary window resizing.
            released_at = time.monotonic()
        time.sleep(0.1)


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    try:
        settle(int(sys.argv[1]), mouse_button_reader())
    except (IndexError, ValueError, RuntimeError, OSError) as error:
        print('Chrome tile recovery: ' + str(error), file=sys.stderr)
        sys.exit(1)
