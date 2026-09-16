#!/usr/bin/env python3
"""Save floating geometry on tile; restore it on float. No background tracking."""
import json
import math
import os
from pathlib import Path
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
        save_cache(cache, key, window['frame'], area)
        run('yabai', '-m', 'window', window['id'], '--toggle', 'float')
        return
    frame = restore_frame(cache.get(key), area)
    # One message applies the toggle and geometry without query/process gaps.
    # Position before size avoids constraining the size against the old edge.
    run('yabai', '-m', 'window', window['id'], '--toggle', 'float',
        '--move', f"abs:{frame['x']}:{frame['y']}",
        '--resize', f"abs:{frame['w']}:{frame['h']}",
        '--move', f"abs:{frame['x']}:{frame['y']}")


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    try:
        toggle(run)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Float toggle: ' + str(error), file=sys.stderr)
        sys.exit(1)
