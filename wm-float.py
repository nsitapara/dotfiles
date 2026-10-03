#!/usr/bin/env python3
"""Save floating geometry on tile; restore it on float. No background tracking."""
import json
import fcntl
import math
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wm_client import run

CACHE = Path.home() / '.local/state/dotfiles-wm/float-frames.json'


def valid(frame):
    return (isinstance(frame, dict)
            and all(isinstance(frame.get(k), (int, float)) and math.isfinite(frame[k])
                    for k in ('x', 'y', 'w', 'h'))
            and frame['w'] > 0 and frame['h'] > 0)


def restore_frame(saved, area, default_scale=0.8):
    if not saved or not valid(saved.get('frame')) or not valid(saved.get('area')):
        w, h = area['w'] * default_scale, area['h'] * default_scale
        return dict(x=round(area['x'] + (area['w'] - w)/2),
                    y=round(area['y'] + (area['h'] - h)/2), w=round(w), h=round(h))
    frame, old = saved['frame'], saved['area']
    w, h = min(frame['w'], area['w']), min(frame['h'], area['h'])
    # Retain pixel size; translate position if the window changed monitors.
    x = area['x'] + (frame['x'] - old['x']) * area['w'] / old['w']
    y = area['y'] + (frame['y'] - old['y']) * area['h'] / old['h']
    return dict(x=round(max(area['x'], min(x, area['x'] + area['w'] - w))),
                y=round(max(area['y'], min(y, area['y'] + area['h'] - h))),
                w=round(w), h=round(h))


def load_cache():
    try:
        cache = json.loads(CACHE.read_text())
        return {key: value for key, value in cache.items()
                if isinstance(value, dict) and isinstance(value.get('at'), (int, float))} if isinstance(cache, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(cache, key, frame, area):
    cache[key] = dict(frame=frame, area=area, at=time.time())
    cache = dict(sorted(cache.items(), key=lambda item: item[1].get('at', 0))[-200:])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_name(CACHE.name + '.' + str(os.getpid()))
    temporary.write_text(json.dumps(cache))
    temporary.replace(CACHE)


def wait_window(query, window, predicate, description, *, stable=False):
    """Wait for yabai's asynchronous AX frame updates for this exact window."""
    deadline = time.monotonic() + 1
    previous = None
    while True:
        current = query('--windows', '--window', window['id'])
        if current.get('id') != window['id'] or current.get('pid') != window['pid']:
            raise RuntimeError('The selected window closed or changed identity')
        if current.get('display') != window['display'] or current.get('space') != window['space']:
            raise RuntimeError('The selected window moved to another desktop; retry floating')
        if predicate(current) and (not stable or current.get('frame') == previous):
            return current
        if time.monotonic() >= deadline:
            raise RuntimeError(description)
        previous = dict(current.get('frame', {}))
        time.sleep(.02)


def frame_matches(actual, expected, keys=('x', 'y', 'w', 'h')):
    return valid(actual) and all(abs(actual[key]-expected[key]) <= 1 for key in keys)


def toggle(run):
    def query(*args):
        return json.loads(run('yabai', '-m', 'query', *args).stdout)
    window = query('--windows', '--window')
    if window.get('is-native-fullscreen') or window.get('has-fullscreen-zoom'):
        raise RuntimeError('Leave fullscreen before toggling floating')
    display = query('--displays', '--display', window['display'])['frame']
    # Use the applied per-space padding, including the laptop's notch clearance.
    padding = {edge: float(run('yabai', '-m', 'config', '--space', window['space'],
                               edge + '_padding').stdout)
               for edge in ('top', 'bottom', 'left', 'right')}
    if any(not math.isfinite(value) or value < 0 for value in padding.values()):
        raise RuntimeError('Invalid workspace padding')
    area = dict(x=display['x'] + padding['left'], y=display['y'] + padding['top'],
                w=display['w'] - padding['left'] - padding['right'],
                h=display['h'] - padding['top'] - padding['bottom'])
    if not valid(area):
        raise RuntimeError('Workspace padding leaves no room for a floating window')
    key = str(window['pid']) + ':' + str(window['id'])
    cache = load_cache()
    if window['is-floating']:
        # Padding queries and an earlier shortcut may have been followed by AX
        # updates. Save a fresh, stable floating frame, never the old tile size.
        current = wait_window(query, window, lambda w: w['is-floating'] and valid(w.get('frame')),
                              'Floating geometry did not settle; retry tiling', stable=True)
        save_cache(cache, key, current['frame'], area)
        run('yabai', '-m', 'window', window['id'], '--toggle', 'float')
        wait_window(query, window, lambda w: not w['is-floating'], 'Window did not return to tiling')
        return
    frame = restore_frame(cache.get(key), area)
    # Move and resize each use yabai's cached full frame. Sending a final move
    # before AX reports the resize can reapply the old tiled dimensions.
    # Establish position first, then resize using the updated frame. No final
    # move is needed, and all operations remain pinned to the original ID.
    run('yabai', '-m', 'window', window['id'], '--toggle', 'float',
        '--move', f"abs:{frame['x']}:{frame['y']}")
    wait_window(query, window, lambda w: w['is-floating'] and frame_matches(w.get('frame'), frame, ('x','y')),
                'Window did not reach its floating position')
    run('yabai', '-m', 'window', window['id'], '--resize', f"abs:{frame['w']}:{frame['h']}")
    wait_window(query, window, lambda w: w['is-floating'] and frame_matches(w.get('frame'), frame),
                'App did not accept the saved floating geometry', stable=True)


def main():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    # Repeated shortcuts cannot observe a half-applied float or overwrite a
    # concurrent save for another window. Each invocation re-queries after lock.
    with CACHE.with_name('float.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            toggle(run)
        finally:
            # yabai emits no signal for float changes; refresh the bar's F badges.
            try:
                subprocess.run(['sketchybar', '--trigger', 'yabai_windows_changed'],
                               capture_output=True, timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass  # The bar is optional.


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Float toggle: ' + str(error), file=sys.stderr)
        sys.exit(1)
