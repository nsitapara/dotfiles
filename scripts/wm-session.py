#!/usr/bin/env python3
"""Carry live window identities and numbered workspaces across WM changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wm_rift as rift

STATE = rift.STATE
run = rift.run


def query_yabai(*args):
    return json.loads(run('yabai', '-m', 'query', *args).stdout)


def aerospace_windows():
    return json.loads(run('aerospace', 'list-windows', '--all', '--json', '--format',
                          '%{window-id} %{app-pid} %{workspace} %{window-layout}').stdout)


def capture(manager):
    if manager == 'rift':
        data = rift.snapshot()
    elif manager == 'yabai':
        spaces = {s['index']: s for s in query_yabai('--spaces')}
        displays = {d['index']: d for d in query_yabai('--displays')}
        windows = []
        for w in query_yabai('--windows'):
            space = spaces.get(w['space'], {})
            label = space.get('label', '')
            if not label.startswith('ws') or not label[2:].isdigit():
                continue
            if (w.get('is-native-fullscreen') or w.get('is-minimized') or w.get('is-hidden')
                    or not w.get('can-move') or w.get('subrole') != 'AXStandardWindow'):
                continue
            windows.append(dict(id=w['id'], pid=w['pid'], workspace=int(label[2:]),
                                display=displays[w['display']]['uuid'], floating=w['is-floating'],
                                focused=w.get('has-focus', False), frame=w['frame'], native_space=w['space']))
        data = dict(manager=manager, windows=windows)
    else:
        result = run('aerospace', 'list-windows', '--focused', '--json', check=False)
        if result.returncode and 'No window is focused' not in result.stderr + result.stdout:
            raise RuntimeError(result.stderr or result.stdout)
        current = json.loads(result.stdout) if result.returncode == 0 else []
        focused = current[0]['window-id'] if current else None
        data = dict(manager=manager, windows=[dict(id=w['window-id'], pid=w['app-pid'],
                    workspace=int(w['workspace']), floating=w['window-layout'] == 'floating',
                    focused=w['window-id'] == focused) for w in aerospace_windows()
                    if str(w['workspace']).isdigit() and 1 <= int(w['workspace']) <= 9])
    data['captured_at'] = time.time()
    rift.write_state('handoff.json', data)


def prepare(manager, target):
    if manager == 'yabai' and target != 'yabai':
        # Virtual WMs take ownership inside the visible native Space. Gather only
        # our numbered desktops; custom-labelled/fullscreen/minimized windows stay put.
        visible = {s['display']: s['index'] for s in query_yabai('--spaces')
                   if s['is-visible'] and not s['is-native-fullscreen']}
        displays = {d['uuid']: d['index'] for d in query_yabai('--displays')}
        saved = rift.read_state('handoff.json', {})
        for w in saved.get('windows', []):
            destination = visible.get(displays.get(w.get('display')))
            if destination is not None and destination != w.get('native_space'):
                run('yabai', '-m', 'window', w['id'], '--space', destination)
    elif manager == 'aerospace':
        # Reveal windows parked off-screen while preserving the captured assignment.
        run('aerospace', 'enable', 'off')


def restore(manager):
    data = rift.read_state('handoff.json')
    if not data or time.time() - data.get('captured_at', 0) > 3600:
        return
    windows = data['windows']
    if manager == 'rift':
        live = rift.snapshot()['windows']
        identities = {(w['id'], w['pid']): w for w in live}
        plan = rift.read_state('display-layout.json')
        slots = rift.mappings(plan)
        for old in windows:
            window = identities.get((old['id'], old['pid']))
            if window is None:
                continue  # It closed while switching; never match by title or app alone.
            number = old['workspace'] if old['workspace'] in slots else min(slots)
            rift.move_window(window, number, True)
            if window['floating'] != old['floating']:
                rift.focus_window(window)
                rift.execute('window', 'toggle-float')
        focused = next((w for w in windows if w['focused'] and (w['id'],w['pid']) in identities), None)
        if focused:
            rift.switch(focused['workspace'] if focused['workspace'] in slots else min(slots), False)
            rift.focus_window(identities[(focused['id'],focused['pid'])])
    elif manager == 'yabai':
        live = {(w['id'],w['pid']): w for w in query_yabai('--windows')}
        labels = {s['label'] for s in query_yabai('--spaces')}
        for w in windows:
            current = live.get((w['id'],w['pid']))
            label = 'ws' + str(w['workspace'])
            if (current is None or label not in labels or not current.get('can-move')
                    or current.get('subrole') != 'AXStandardWindow'):
                continue
            run('yabai', '-m', 'window', w['id'], '--space', label)
            if current['is-floating'] != w['floating']:
                run('yabai', '-m', 'window', w['id'], '--toggle', 'float')
            if w['floating'] and w.get('frame'):
                f = w['frame']
                run('yabai', '-m', 'window', w['id'], '--move', f"abs:{int(f['x'])}:{int(f['y'])}",
                    '--resize', f"abs:{int(f['w'])}:{int(f['h'])}")
        focused = next((w for w in windows if w['focused'] and (w['id'],w['pid']) in live), None)
        if focused and 'ws'+str(focused['workspace']) in labels:
            run(sys.executable, ROOT/'yabai/.config/yabai/scripts/focus-space.py', 'ws'+str(focused['workspace']))
            run('yabai', '-m', 'window', '--focus', focused['id'])
    else:
        run('aerospace', 'enable', 'on')
        live = {(w['window-id'], w['app-pid']): w for w in aerospace_windows()}
        for w in windows:
            if (w['id'],w['pid']) not in live:
                continue
            run('aerospace', 'move-node-to-workspace', str(w['workspace']), '--window-id', w['id'])
            run('aerospace', 'layout', '--window-id', w['id'], 'floating' if w['floating'] else 'tiling')
        focused = next((w for w in windows if w['focused'] and (w['id'],w['pid']) in live), None)
        if focused:
            run('aerospace', 'workspace', str(focused['workspace']))
            run('aerospace', 'focus', '--window-id', focused['id'])


if __name__ == '__main__':
    try:
        command, manager, *args = sys.argv[1:]
        {'capture': capture, 'prepare': prepare, 'restore': restore}[command](manager, *args)
    except (RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print('Window handoff: ' + str(error), file=sys.stderr)
        sys.exit(1)
