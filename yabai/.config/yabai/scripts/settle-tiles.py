#!/usr/bin/env python3
"""Reapply tiles that overlap or leave empty screen.

Chrome mode waits for a detached tab's mouse-up. Space mode checks every visible
BSP Space after windows leave or Spaces change: a window that missed its resize
is reflushed, and a tile left behind by a window yabai no longer tracks (its
Space re-check skips unknown windows) is removed by rebuilding the tree.
"""
import ctypes
import fcntl
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
    # A lone root tile reports split-type "none"; floating windows are excluded below.
    return (window.get('is-visible') and window.get('subrole') == 'AXStandardWindow'
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


def uncovered(tiles, area, gap):
    # ponytail: 16x16 sample grid, misses slivers under 1/16 of the Space.
    pad = gap / 2 + 2
    for i in range(16):
        for j in range(16):
            x = area['x'] + (i + .5) * area['w'] / 16
            y = area['y'] + (j + .5) * area['h'] / 16
            if not any(t['frame']['x'] - pad <= x <= t['frame']['x'] + t['frame']['w'] + pad
                       and t['frame']['y'] - pad <= y <= t['frame']['y'] + t['frame']['h'] + pad
                       for t in tiles):
                return True
    return False


def broken(index):
    """Return None, 'overlap', or 'uncovered' for a visible BSP Space."""
    space = query('--spaces', '--space', index)
    if not space or space['type'] != 'bsp' or not space.get('is-visible'):
        return None
    windows = query('--windows', '--space', index)
    if not windows or any(w.get('has-parent-zoom') or w.get('has-fullscreen-zoom') for w in windows):
        return None
    tiles = [w for w in windows if tiled(w)]
    if not tiles:
        return None
    if any(overlaps(a, b) for i, a in enumerate(tiles) for b in tiles[i + 1:]):
        return 'overlap'
    display = query('--displays', '--display', space['display'])
    if not display:
        return None
    config = {key: float(run('yabai', '-m', 'config', '--space', index, key, timeout=2).stdout)
              for key in ('top_padding', 'bottom_padding', 'left_padding', 'right_padding', 'window_gap')}
    frame = display['frame']
    area = {'x': frame['x'] + config['left_padding'], 'y': frame['y'] + config['top_padding'],
            'w': frame['w'] - config['left_padding'] - config['right_padding'],
            'h': frame['h'] - config['top_padding'] - config['bottom_padding']}
    return 'uncovered' if uncovered(tiles, area, config['window_gap']) else None


def settle_space(index, button_down):
    if not broken(index) or button_down():
        return
    run('yabai', '-m', 'space', index, '--padding', 'rel:0:0:0:0', timeout=2)
    time.sleep(.5)
    # ponytail: an app that refuses to grow also stays uncovered and resets
    # this Space's split ratios; exempt such apps if that ever happens.
    if broken(index) == 'uncovered' and not button_down():
        run('yabai', '-m', 'space', index, '--layout', 'bsp', timeout=2)


def settle_visible(button_down):
    """Drain requests from bursts of events with one worker."""
    state = Path.home() / '.local/state/dotfiles-wm'
    state.mkdir(parents=True, exist_ok=True)
    pending = state / 'settle-tiles.pending'
    pending.touch()
    with (state / 'settle-tiles.lock').open('a+') as lock:
        while pending.exists():
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # The running worker sees this request.
            while pending.exists():
                pending.unlink(missing_ok=True)
                time.sleep(.3)  # Let yabai's own relayout land first.
                for space in query('--spaces') or []:
                    if space.get('is-visible'):
                        settle_space(space['index'], button_down)
            fcntl.flock(lock, fcntl.LOCK_UN)


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
        if sys.argv[1:] == ['--spaces']:
            settle_visible(mouse_button_reader())
        else:
            settle(int(sys.argv[1]), mouse_button_reader())
    except (IndexError, ValueError, RuntimeError, OSError) as error:
        print('Tile recovery: ' + str(error), file=sys.stderr)
        sys.exit(1)
