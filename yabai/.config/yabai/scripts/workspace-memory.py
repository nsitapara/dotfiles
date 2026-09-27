#!/usr/bin/env python3
"""Remember each window's workspace and put windows back after display changes.

macOS merges, moves and recreates desktops on hotplug, so desktops cannot say
where a window belongs. Window IDs survive, so the workspace is saved per ID,
but only while the applied layout is intact. Hotplug churn never overwrites it.
"""
import fcntl
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from wm_client import run

STATE = Path.home() / '.local/state/dotfiles-wm'
MEMORY = STATE / 'workspace-memory.json'
LAYOUT = STATE / 'display-layout.json'


def query(*args):
    result = run('yabai', '-m', 'query', *args, check=False, timeout=2)
    return json.loads(result.stdout) if result.returncode == 0 else None


def settled(spaces, displays, layout):
    """True when the screens and every workspace label match the applied layout."""
    if not layout or {d['id']: d['index'] for d in displays} != {s['id']: s['index'] for s in layout}:
        return False
    labels = {s['label']: s['display'] for s in spaces if s.get('label')}
    return all(labels.get(f'ws{n}') == screen['index']
               for screen in layout for n in screen['workspaces'])


def placements(spaces, windows):
    labels = {s['index']: s['label'] for s in spaces if s.get('label', '').startswith('ws')}
    return {str(w['id']): labels[w['space']] for w in windows
            if w.get('space') in labels and not w.get('is-sticky')}


def moves(memory, spaces, windows):
    """(window, label) pairs for remembered windows away from an existing workspace."""
    present = {s['label'] for s in spaces if s.get('label')}
    current = placements(spaces, windows)
    return [(int(wid), label) for wid, label in memory.items()
            if label in present and current.get(wid) != label
            and any(str(w['id']) == wid for w in windows)]


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def main(action):
    if action == 'restore' and not MEMORY.exists():
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / 'workspace-memory.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        spaces, windows = query('--spaces'), query('--windows')
        if spaces is None or windows is None:
            return 1
        if action == 'save':
            displays = query('--displays')
            if displays is None or not settled(spaces, displays, load(LAYOUT)):
                return 0
            temp = MEMORY.with_suffix('.tmp')
            temp.write_text(json.dumps(placements(spaces, windows)))
            os.replace(temp, MEMORY)
        elif action == 'restore':
            for window, label in moves(load(MEMORY) or {}, spaces, windows):
                if run('yabai', '-m', 'window', str(window), '--space', label,
                       check=False, timeout=2).returncode == 0:
                    print(f'Restored window {window} to {label}.')
        else:
            print('Usage: workspace-memory.py save|restore', file=sys.stderr)
            return 64
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
