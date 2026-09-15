#!/usr/bin/env python3
"""Swap a tiled neighbor; at a workspace edge, give this window its own side."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DIRECTIONS = {'left': 'west', 'right': 'east', 'up': 'north', 'down': 'south'}
OPPOSITE = {'north': 'south', 'south': 'north', 'west': 'east', 'east': 'west'}


def run(*args, check=True):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Command failed: ' + ' '.join(map(str, args)))
    return result


def query(*args):
    return json.loads(run('yabai', '-m', 'query', *args).stdout)


def window(id, *args):
    return run('yabai', '-m', 'window', id, *args)


def eligible(w):
    return not any(w.get(key, False) for key in (
        'is-floating', 'is-minimized', 'is-hidden', 'is-sticky',
        'is-native-fullscreen', 'has-fullscreen-zoom', 'has-parent-zoom'))


def neighbor(selected, windows, direction):
    """Only candidates in this tiling area with overlap across the other axis."""
    axis, size, cross, extent = ('x', 'w', 'y', 'h') if direction in ('left', 'right') else ('y', 'h', 'x', 'w')
    positive = direction in ('right', 'down')
    f = selected['frame']
    candidates = []
    for w in windows:
        if w['id'] == selected['id']:
            continue
        g = w['frame']
        overlap = min(f[cross]+f[extent], g[cross]+g[extent]) - max(f[cross], g[cross])
        distance = g[axis]-(f[axis]+f[size]) if positive else f[axis]-(g[axis]+g[size])
        if overlap > 1 and distance >= -1:
            center = abs(f[cross]+f[extent]/2-g[cross]-g[extent]/2)
            candidates.append((distance, center, w['id'], w))
    return min(candidates, key=lambda c: c[:3])[-1] if candidates else None


def spans_side(selected, windows, direction):
    axis, size = ('y', 'h') if direction in ('left', 'right') else ('x', 'w')
    low = min(w['frame'][axis] for w in windows)
    high = max(w['frame'][axis]+w['frame'][size] for w in windows)
    f = selected['frame']
    return abs(f[axis]-low) <= 2 and abs(f[axis]+f[size]-high) <= 2


def insert(id, direction):
    # --insert toggles an existing identical hint off. Set a different hint first.
    window(id, '--insert', OPPOSITE[direction])
    window(id, '--insert', direction)


def settled_windows(space, ids):
    # macOS sends frame updates after yabai acknowledges a layout command.
    # Wait for non-overlapping, stable frames before deriving another action.
    previous = None
    for _ in range(25):
        time.sleep(0.04)
        windows = [w for w in query('--windows', '--space', space) if w['id'] in ids]
        if {w['id'] for w in windows} != ids:
            raise RuntimeError('Windows changed during rearrangement; stopped.')
        overlap = False
        for i, a in enumerate(windows):
            f = a['frame']
            for b in windows[i+1:]:
                g = b['frame']
                if (min(f['x']+f['w'],g['x']+g['w'])-max(f['x'],g['x']) > 2 and
                        min(f['y']+f['h'],g['y']+g['h'])-max(f['y'],g['y']) > 2):
                    overlap = True
        snapshot = sorted((w['id'], tuple(w['frame'][a] for a in ('x','y','w','h'))) for w in windows)
        if not overlap and snapshot == previous:
            return windows
        previous = snapshot
    raise RuntimeError('Window frames have not settled; stopped.')


def yabai(direction, id=None):
    selected = query('--windows', '--window', *([id] if id else []))
    id = selected['id']
    if not eligible(selected):
        return
    space = query('--spaces', '--space', selected['space'])
    if space['type'] != 'bsp':
        return
    all_windows = query('--windows', '--space', selected['space'])
    if any(w.get('has-fullscreen-zoom') or w.get('has-parent-zoom') for w in all_windows):
        return
    windows = [w for w in all_windows
               if eligible(w) and w['display'] == selected['display']]
    # Preserve deliberate stacks; promoting a stack needs separate semantics.
    if len(windows) < 2 or any(w.get('stack-index', 0) for w in windows):
        return
    target = neighbor(selected, windows, direction)
    if target:
        window(id, '--swap', target['id'])
        settled_windows(selected['space'], {w['id'] for w in windows})
        return
    if spans_side(selected, windows, direction):
        return

    horizontal = direction in ('left', 'right')
    order = ('y', 'x') if horizontal else ('x', 'y')
    others = sorted((w for w in windows if w['id'] != id),
                    key=lambda w: tuple(w['frame'][a] for a in order))
    anchor = others[0]['id']
    # Gather every other leaf beside the anchor. The selected leaf is never
    # removed, floated, or sent to another Space. It becomes a root-level tile.
    for other in others[1:]:
        insert(anchor, 'south' if horizontal else 'east')
        window(other['id'], '--warp', anchor)
    current = query('--windows', '--window', id)
    desired_split = 'vertical' if horizontal else 'horizontal'
    if current['split-type'] != desired_split:
        window(id, '--toggle', 'split')
    current = query('--windows', '--window', id)
    desired_child = 'first_child' if direction in ('left', 'up') else 'second_child'
    if current['split-child'] != desired_child:
        run('yabai', '-m', 'space', selected['space'], '--mirror', 'y-axis' if horizontal else 'x-axis')
    window(id, '--ratio', 'abs:0.5')

    # Natural warp chooses the nearest half. Restore the other apps' reading order
    # with swaps, which preserve the new geometry and keep focus on the selection.
    fresh = settled_windows(selected['space'], {w['id'] for w in windows})
    other_ids = {w['id'] for w in others}
    slots = sorted((w for w in fresh if w['id'] in other_ids),
                   key=lambda w: tuple(w['frame'][a] for a in order))
    ids = [w['id'] for w in slots]
    for i, desired in enumerate(w['id'] for w in others):
        if ids[i] != desired:
            j = ids.index(desired)
            window(desired, '--swap', ids[i])
            ids[i], ids[j] = ids[j], ids[i]
    settled_windows(selected['space'], {w['id'] for w in windows})


def aerospace(direction, id=None):
    rows = json.loads(run('aerospace', 'list-windows', '--all' if id else '--focused', '--json',
                          '--format', '%{window-id} %{workspace} %{window-layout} %{window-is-fullscreen}').stdout)
    if id:
        rows = [w for w in rows if w['window-id'] == id]
    if not rows:
        return
    selected = rows[0]
    id = id or selected['window-id']
    if selected['window-layout'] not in ('h_tiles', 'v_tiles', 'h_accordion', 'v_accordion') or str(selected['window-is-fullscreen']).lower() == 'true':
        return
    result = run('aerospace', 'swap', '--window-id', id, direction, check=False)
    if result.returncode == 0:
        return
    # A real command failure is not evidence that we reached an edge.
    if result.stderr.strip():
        raise RuntimeError(result.stderr.strip())
    workspace = selected['workspace']
    run('aerospace', 'flatten-workspace-tree', '--workspace', workspace)
    run('aerospace', 'layout', '--workspace', workspace, '--root',
        'v_tiles' if direction in ('left', 'right') else 'h_tiles')
    run('aerospace', 'move', '--window-id', id, '--boundaries', 'workspace',
        '--boundaries-action', 'create-implicit-container',
        '--fail-if-fullscreen', '--fail-if-macos-native-fullscreen', direction)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manager', choices=['yabai', 'aerospace'])
    parser.add_argument('direction', choices=DIRECTIONS)
    parser.add_argument('--window-id', type=int)
    args = parser.parse_args()
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    state = Path.home()/'.local/state/dotfiles-wm'
    state.mkdir(parents=True, exist_ok=True)
    with (state/'direction.lock').open('w') as lock:
        try:
            # Drop auto-repeat while a rearrangement is still running.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            (yabai if args.manager == 'yabai' else aerospace)(args.direction, args.window_id)
        except (RuntimeError, ValueError, KeyError) as error:
            print('Window move: ' + str(error), file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
