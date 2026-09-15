#!/usr/bin/env python3
"""Step the selected tiled column through width presets, without rearranging it."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys

# Fractions of the two columns' usable width, excluding the gap.
PRESETS = (0.50, 0.65, 0.75)
TOLERANCE = 2


def resize_plan(selected, windows, step):
    """Recognize two aligned columns; decline overlaps and ambiguous layouts."""
    columns = []
    for window in sorted(windows, key=lambda w: w['frame']['x']):
        frame = window['frame']
        if frame['w'] <= 0 or frame['h'] <= 0:
            return None
        if columns and abs(frame['x'] - columns[-1][0]['frame']['x']) <= TOLERANCE:
            columns[-1].append(window)
        else:
            columns.append([window])
    if len(columns) != 2:
        return None
    bounds = []
    for column in columns:
        first = column[0]['frame']
        if any(abs(w['frame']['w'] - first['w']) > TOLERANCE for w in column):
            return None
        rows = sorted(column, key=lambda w: w['frame']['y'])
        if any(a['frame']['y'] + a['frame']['h'] > b['frame']['y'] + TOLERANCE
               for a, b in zip(rows, rows[1:])):
            return None
        bounds.append((rows[0]['frame']['y'], rows[-1]['frame']['y'] + rows[-1]['frame']['h']))
    left, right = (column[0]['frame'] for column in columns)
    if (left['x'] + left['w'] > right['x'] + TOLERANCE
            or any(abs(a-b) > TOLERANCE for a, b in zip(*bounds))):
        return None
    side = next((i for i, column in enumerate(columns)
                 if any(w['id'] == selected['id'] for w in column)), None)
    if side is None:
        return None
    width = selected['frame']['w']
    total = left['w'] + right['w']
    targets = [round(total * ratio) for ratio in PRESETS]
    candidates = [target for target in targets
                  if (target-width)*step > TOLERANCE]
    if not candidates:
        return None
    target = min(candidates) if step > 0 else max(candidates)
    return ('right' if side == 0 else 'left'), round(target-width)


def resize_yabai(wm, step):
    selected = wm.query('--windows', '--window')
    if not wm.eligible(selected):
        return
    space = wm.query('--spaces', '--space', selected['space'])
    if space['type'] != 'bsp':
        return
    rows = wm.query('--windows', '--space', selected['space'])
    if any(w.get('has-fullscreen-zoom') or w.get('has-parent-zoom') for w in rows):
        return
    windows = [w for w in rows if wm.eligible(w) and w['display'] == selected['display']]
    if any(w.get('stack-index') for w in windows):
        return
    plan = resize_plan(selected, windows, step)
    if plan:
        edge, delta = plan
        wm.window(selected['id'], '--resize', f'{edge}:{delta if edge == "right" else -delta}:0')


def resize_aerospace(wm, step):
    def rows(*args):
        return json.loads(wm.run('aerospace', 'list-windows', *args, '--json',
                                 '--format', wm.AS_FORMAT).stdout)
    focused = rows('--focused')
    if not focused or focused[0]['window-layout'] not in ('h_tiles', 'v_tiles'):
        return
    selected = focused[0]
    if not wm.aerospace_tiled(selected):
        return
    workspace = rows('--workspace', selected['workspace'])
    if any(w['window-layout'] in ('h_accordion', 'v_accordion') or
           str(w['window-is-fullscreen']).lower() == 'true' for w in workspace):
        return
    frames = {w['id']: w['frame'] for w in wm.desktop_geometry()['windows']}
    tiled = [w for w in workspace if wm.aerospace_tiled(w)]
    if any(w['window-id'] not in frames for w in tiled):
        return
    windows = [dict(id=w['window-id'], frame=frames[w['window-id']]) for w in tiled]
    plan = resize_plan(dict(id=selected['window-id'], frame=frames[selected['window-id']]), windows, step)
    if plan:
        # Relative pixels also resize an ancestor column containing stacked rows.
        wm.run('aerospace', 'resize', '--window-id', selected['window-id'], 'width', f'{plan[1]:+d}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manager', choices=['yabai', 'aerospace'])
    parser.add_argument('step', choices=['up', 'down'])
    args = parser.parse_args()
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    spec = importlib.util.spec_from_file_location('wm_direction', Path(__file__).with_name('wm-direction.py'))
    wm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wm)
    state = Path.home() / '.local/state/dotfiles-wm'
    state.mkdir(parents=True, exist_ok=True)
    # Share the directional move lock so a preset cannot resize mid-rearrangement.
    with (state / 'direction.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        (resize_yabai if args.manager == 'yabai' else resize_aerospace)(wm, 1 if args.step == 'up' else -1)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Window size: ' + str(error), file=sys.stderr)
        sys.exit(1)
