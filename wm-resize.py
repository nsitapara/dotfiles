#!/usr/bin/env python3
"""Resize a window through one consistent edge, without probing outer fences."""
import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import sys


def resize(wm, axis, delta):
    selected = wm.query('--windows', '--window')
    if any(selected.get(key) for key in ('is-minimized', 'is-hidden',
                                         'is-native-fullscreen', 'has-fullscreen-zoom', 'has-parent-zoom')):
        return
    positive, negative, split = (('right', 'left', 'vertical') if axis == 'width'
                                 else ('bottom', 'top', 'horizontal'))
    if selected.get('is-floating'):
        edge = positive
    elif selected.get('split-type') == split:
        # The tree's child order is stable across odd-pixel rounding and app
        # minimum sizes. A right/bottom child must move its left/top divider.
        child = selected.get('split-child')
        if child not in ('first_child', 'second_child'):
            return
        edge = positive if child == 'first_child' else negative
    else:
        # A row inside a column may need to resize an ancestor's divider.
        windows = [w for w in wm.query('--windows', '--space', selected['space'])
                   if wm.eligible(w) and w['display'] == selected['display']]
        directions = ('right', 'left') if axis == 'width' else ('down', 'up')
        if wm.neighbor(selected, windows, directions[0], allow_overlap=True):
            edge = positive
        elif wm.neighbor(selected, windows, directions[1], allow_overlap=True):
            edge = negative
        else:
            return
    change = delta if edge == positive else -delta
    offsets = f'{change}:0' if axis == 'width' else f'0:{change}'
    wm.window(selected['id'], '--resize', f'{edge}:{offsets}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('axis', choices=['width', 'height'])
    parser.add_argument('delta', type=int)
    args = parser.parse_args()
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    spec = importlib.util.spec_from_file_location('wm_direction', Path(__file__).with_name('wm-direction.py'))
    wm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wm)
    state = Path.home()/'.local/state/dotfiles-wm'
    state.mkdir(parents=True, exist_ok=True)
    with (state/'direction.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        resize(wm, args.axis, args.delta)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Window resize: ' + str(error), file=sys.stderr)
        sys.exit(1)
