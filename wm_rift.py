#!/usr/bin/env python3
"""Rift adapter for the shared desktop, workspace numbers, shortcuts and bar."""
import json
import os
from pathlib import Path
import re
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
STATE = Path(os.environ.get('DOTFILES_WM_STATE_DIR', Path.home() / '.local/state/dotfiles-wm'))
os.environ['PATH'] += ':' + str(Path.home() / '.local/bin') + ':/opt/homebrew/bin:/usr/local/bin'


def run(*args, check=True, input=None):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                            input=input, timeout=30)
    if check and result.returncode:
        raise RuntimeError(' '.join(str(a) for a in args) + ': ' + (result.stderr.strip() or result.stdout.strip() or 'failed'))
    return result


def query(what, space=None):
    args = ('--space-id', str(space)) if space is not None else ()
    return json.loads(run('rift-cli', 'query', what, *args).stdout)


def execute(*args):
    output = run('rift-cli', 'execute', *args).stdout
    # Some commands report semantic failures on stdout with exit status zero.
    if 'Could not' in output or 'Error:' in output:
        raise RuntimeError(output.strip())
    return output


def write_state(name, value):
    STATE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=STATE, delete=False) as stream:
        json.dump(value, stream)
        path = Path(stream.name)
    path.chmod(0o600)
    path.replace(STATE / name)


def read_state(name, default=None):
    try:
        return json.loads((STATE / name).read_text())
    except (FileNotFoundError, ValueError):
        return default


def rect(frame):
    return dict(x=frame['origin']['x'], y=frame['origin']['y'],
                w=frame['size']['width'], h=frame['size']['height'])


def display_plan(displays=None):
    displays = displays if displays is not None else query('displays')
    helper = ROOT / 'yabai/.config/yabai/scripts/build-spaces-helper.sh'
    run(helper)
    metadata = json.loads(run(Path.home() / 'Applications/Dotfiles Spaces.app/Contents/MacOS/Dotfiles Spaces', '--display-info').stdout)
    screens = []
    for index, display in enumerate(displays):
        matches = [m for m in metadata if m['id'] == display['screen_id']]
        if len(matches) != 1:
            raise RuntimeError('Display metadata has not settled')
        screens.append(dict(matches[0], index=index, uuid=display['uuid'], frame=rect(display['frame'])))
    pin = STATE / 'display-profile.pin'
    prefs = ROOT / 'scripts/wm/display-preferences.json'
    output = run('jq', '-e', '--arg', 'profile', pin.read_text().strip() if pin.exists() else 'auto',
                 '--argjson', 'prefs', prefs.read_text(), '-f', ROOT / 'scripts/wm/display-layout.jq',
                 input=json.dumps(screens)).stdout
    return json.loads(output)


def mappings(plan):
    # Global number N always maps to local Rift slot N-1. This remains stable
    # across docking changes, even though Rift creates slots per native Space.
    return {number: screen for screen in plan for number in screen['workspaces']}


def snapshot():
    displays = query('displays')
    windows = []
    seen = set()
    for display in displays:
        spaces = set(display['active_space_ids'])
        if display.get('space') is not None:
            spaces.add(display['space'])
        for space in sorted(spaces):
            for workspace in query('workspaces', space):
                for window in workspace['windows']:
                    wsid = window.get('window_server_id')
                    if wsid is None or wsid in seen:
                        continue
                    seen.add(wsid)
                    windows.append(dict(id=wsid, pid=window['id']['pid'], rift_id=window['id'],
                                        workspace=workspace['index'] + 1, display=display['uuid'],
                                        space=space, floating=window['is_floating'],
                                        visible=workspace['is_active'] and space == display.get('space'),
                                        focused=window['is_focused'], frame=rect(window['frame'])))
    return dict(manager='rift', windows=windows, displays=displays)


def focus_window(window):
    if window.get('display'):
        displays = query('displays')
        if not any(d['uuid'] == window['display'] and d['is_active_context'] for d in displays):
            focus_display(window['display'])
    execute('window', 'focus', '--window-id', json.dumps(window['rift_id']),
            '--window-server-id', window['id'])
    wait_for(lambda: json.loads(run('rift-cli', 'query', 'window', json.dumps(window['rift_id'])).stdout).get('is_focused'),
             'Rift did not focus the selected window')


def wait_for(predicate, description):
    for _ in range(30):
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError(description)


def focus_display(uuid):
    target = next(d for d in query('displays') if d['uuid'] == uuid)
    if target.get('space') is None:
        raise RuntimeError('Rift has no manageable desktop on ' + target.get('name', uuid)
                           + '. Leave macOS native fullscreen on that monitor, then retry.')
    execute('display', 'focus', '--uuid', uuid)
    displays = query('displays')
    target = next(d for d in displays if d['uuid'] == uuid)
    if not target['is_active_context']:
        # Rift 0.5.9 only warps the pointer when the active workspace is empty.
        # Focus a tracked window on that display to establish its command context.
        workspaces = query('workspaces', target['space'])
        candidates = [w for ws in sorted(workspaces, key=lambda ws: not ws['is_active']) for w in ws['windows']]
        if candidates:
            window = candidates[0]
            focus_window(dict(rift_id=window['id'], id=window['window_server_id']))
        else:
            from scripts.wm.focus_empty_display import click_empty_desktop
            click_empty_desktop(rect(target['frame']))
    return wait_for(lambda: next((d for d in query('displays') if d['uuid'] == uuid and d['is_active_context']), None),
                    'Rift could not focus the empty display. Click its desktop once, then retry.')


def current_slot():
    displays = query('displays')
    current = next((d for d in displays if d['is_active_context']), None)
    if current is None or current.get('space') is None:
        raise RuntimeError('No active Rift display')
    ws = next((w for w in query('workspaces', current['space']) if w['is_active']), None)
    if ws is None:
        raise RuntimeError('No active Rift workspace')
    return current, ws


def switch(number, remember=True):
    plan = read_state('display-layout.json') or display_plan()
    target = mappings(plan).get(int(number))
    if target is None:
        raise RuntimeError(f'Workspace {number} is unavailable in this display profile')
    if remember:
        current, workspace = current_slot()
        previous = workspace['index'] + 1
        if previous != int(number) or current['uuid'] != target['uuid']:
            write_state('rift-previous-workspace.json', previous)
    display = focus_display(target['uuid'])
    if not display['is_active_space']:
        execute('space', 'toggle-activated')
    execute('workspace', 'switch', int(number) - 1)
    wait_for(lambda: any(w['index'] == int(number)-1 and w['is_active'] for w in query('workspaces', display['space'])),
             'Rift did not switch to the requested workspace')


def move_window(window, number, follow=False):
    plan = read_state('display-layout.json') or display_plan()
    target = mappings(plan).get(int(number))
    if target is None:
        raise RuntimeError(f'Workspace {number} is unavailable in this display profile')
    original, original_ws = current_slot()
    focus_window(window)
    if window['display'] != target['uuid']:
        execute('display', 'move-window', '--uuid', target['uuid'], '--window-id', window['rift_id']['idx'])
        wait_for(lambda: any(w['id'] == window['id'] and w['display'] == target['uuid'] for w in snapshot()['windows']),
                 'Window did not move to the requested monitor')
        window['display'] = target['uuid']
    # MoveWindow resolves the specified window in its current display context.
    focus_display(target['uuid'])
    execute('workspace', 'move-window', int(number)-1, window['rift_id']['idx'], *(['--follow'] if follow else []))
    wait_for(lambda: any(w['id'] == window['id'] and w['workspace'] == int(number) and w['display'] == target['uuid']
                        for w in snapshot()['windows']), 'Window did not reach the requested workspace')
    if follow:
        switch(number, remember=False)
        # Switching the workspace can select another resident window. Follow
        # this exact window before any caller starts rearranging the layout.
        focus_window(window)
    else:
        focus_display(original['uuid'])
        execute('workspace', 'switch', original_ws['index'])


def release():
    # Bring every virtual workspace's windows into its native Space's first slot
    # before deactivation. Quit alone leaves inactive groups hidden/offscreen.
    windows = snapshot()['windows']
    for window in windows:
        focus_window(window)
        execute('workspace', 'move-window', 0, window['rift_id']['idx'], '--follow')
    for display in query('displays'):
        focus_display(display['uuid'])
        execute('workspace', 'switch', 0)



def profile():
    before = display_plan()
    time.sleep(.25)
    if before != display_plan():
        raise RuntimeError('Display layout is changing; retry after it settles')
    write_state('display-layout.json', before)
    for screen in before:
        execute('config', 'set', 'settings.layout.gaps.per_display.' + screen['uuid'],
                json.dumps({'outer': {'top': screen['top_padding'], 'bottom': 8, 'left': 10, 'right': 10}}))
    # Ensure every display starts at one of its owned numbered workspaces.
    focused, _ = current_slot()
    for display in query('displays'):
        screen = next(p for p in before if p['uuid'] == display['uuid'])
        if not screen['workspaces']:
            continue
        focus_display(display['uuid'])
        if not display['is_active_space']:
            execute('space', 'toggle-activated')
        _, ws = current_slot()
        if ws['index'] + 1 not in screen['workspaces']:
            execute('workspace', 'switch', screen['workspaces'][0] - 1)
    # Rehome existing numbered windows only where the profile actually changed.
    for window in snapshot()['windows']:
        owner = mappings(before).get(window['workspace'])
        if owner and owner['uuid'] != window['display']:
            move_window(window, window['workspace'])
    focus_display(focused['uuid'])
    package = 'sketchybar-docked' if len(before) > 1 else 'sketchybar'
    live = Path.home() / '.config/sketchybar/sketchybarrc'
    expected = ROOT / package / '.config/sketchybar/sketchybarrc'
    if live.resolve() != expected:
        run('stow', '--dir=' + str(ROOT), '--target=' + str(Path.home()), '-D', 'sketchybar', 'sketchybar-docked')
        run('stow', '--dir=' + str(ROOT), '--target=' + str(Path.home()), package)
    if run('pgrep', '-x', 'sketchybar', check=False).returncode == 0:
        run('sketchybar', '--set', 'display_mode', 'label=reloading', check=False)
        run('sketchybar', '--reload', live)
        mode = 'docked' if len(before) > 1 else 'non-docked'
        for _ in range(60):
            result = run('sketchybar', '--query', 'display_mode', check=False)
            try:
                loaded = json.loads(result.stdout).get('label', {}).get('value') if result.returncode == 0 else None
            except ValueError:
                loaded = None
            if loaded == mode:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('SketchyBar did not load the Rift display profile')
    print('Rift display profile applied.')


def permission_probe():
    # A launchd child needs its own Accessibility grant; a process launched by
    # an already-trusted terminal can inherit trust and give a false positive.
    if run('pgrep', '-x', 'rift', check=False).returncode == 0:
        return
    with tempfile.TemporaryDirectory(prefix='rift-permission-') as temp:
        folder = Path(temp)
        config = folder / 'config.toml'
        config.write_text('[settings]\ndefault_disable = true\n[settings.ui.menu_bar]\nenabled = false\n[keys]\n')
        label = 'local.dotfiles.rift-permission'
        plist = folder / (label + '.plist')
        job = 'gui/' + str(os.getuid()) + '/' + label
        plist.write_bytes(plistlib.dumps({
            'Label': label, 'RunAtLoad': True,
            'ProgramArguments': [str(Path(shutil.which('rift')).resolve()), '--config', str(config)],
            'StandardOutPath': str(folder/'out.log'), 'StandardErrorPath': str(folder/'err.log'),
        }))
        run('launchctl', 'bootstrap', 'gui/' + str(os.getuid()), plist)
        try:
            for _ in range(35):
                try:
                    result = subprocess.run(['rift-cli','query','displays'],capture_output=True,text=True,timeout=1)
                    if result.returncode == 0 and isinstance(json.loads(result.stdout), list):
                        return
                except (subprocess.TimeoutExpired, ValueError):
                    pass
                time.sleep(.25)
            raise RuntimeError('Grant Rift Device Control and Data Access in System Settings, then retry. Current manager was kept running.')
        finally:
            run('launchctl', 'bootout', job)
            for _ in range(30):
                if run('pgrep','-x','rift',check=False).returncode != 0:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Rift permission-check process did not stop')


def preflight():
    version = run('rift', '--version').stdout
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (0, 5, 9):
        raise RuntimeError('Rift 0.5.9 or newer is required. Run ./wm.sh install rift.')
    for name in ('config.toml', 'skhdrc', 'sketchybar.lua'):
        if not (ROOT / 'rift/.config/rift' / name).is_file():
            raise RuntimeError('Incomplete Rift configuration: ' + name)
    permission_probe()


def event():
    payload = json.loads(sys.argv[-1]) if len(sys.argv) > 2 else {}
    if payload.get('type') == 'focused_window_changed':
        identity = payload['window_id']
        window = json.loads(run('rift-cli', 'query', 'window', json.dumps(identity)).stdout)
        if window and window.get('window_server_id'):
            focused = dict(id=window['window_server_id'], pid=identity['pid'])
            history = read_state('rift-focus.json', [])
            if not history or history[-1]['id'] != focused['id']:
                write_state('rift-focus.json', [w for w in history if w['id'] != focused['id']][-1:] + [focused])
    run('sketchybar', '--trigger', 'rift_changed', check=False)


def bar():
    plan = read_state('display-layout.json') or display_plan()
    result = dict(spaces=[], windows=[], displays=[], targets=[], layout=plan,
                  bar_displays=json.loads(run('sketchybar', '--query', 'displays').stdout))
    for display in query('displays'):
        owner = next((p for p in plan if p['uuid'] == display['uuid']), None)
        if not owner or display.get('space') is None:
            continue
        result['displays'].append(dict(index=owner['index'], id=display['screen_id'], frame=rect(display['frame'])))
        for workspace in query('workspaces', display['space']):
            number = workspace['index'] + 1
            # Keep unexpected occupied slots reachable instead of hiding windows.
            if number not in owner['workspaces'] and not workspace['windows']:
                continue
            index = display['screen_id']*100 + number
            result['spaces'].append(dict(index=index, display=owner['index'],
                label='ws'+str(number) if number in owner['workspaces'] else '',
                **{'has-focus': workspace['is_active'] and display['is_active_context'], 'is-native-fullscreen': False}))
            result['targets'].append(dict(index=index, number=number, uuid=display['uuid']))
            result['windows'].extend(dict(id=w['window_server_id'], space=index, app=w.get('app_name'))
                                     for w in workspace['windows'] if w.get('window_server_id'))
    print(json.dumps(result))


def action(args):
    command = args[0]
    if command == 'workspace-display':
        # Clicks include the actual display, including unexpected occupied slots.
        number, uuid = int(args[1]), args[2]
        if not 1 <= number <= 9 or not re.fullmatch(r'[0-9A-Fa-f-]+', uuid):
            raise RuntimeError('Invalid workspace target')
        display = focus_display(uuid)
        execute('workspace', 'switch', number-1)
        wait_for(lambda: any(w['index'] == number-1 and w['is_active'] for w in query('workspaces', display['space'])),
                 'Rift did not activate the clicked workspace')
        return
    if command in ('focus', 'move'):
        from scripts.wm.rift_geometry import directional
        directional(sys.modules[__name__], args[1], move=command == 'move')
        return
    if command == 'display' and '--focus' in args:
        current, _ = current_slot()
        displays = sorted(query('displays'), key=lambda d: (d['frame']['origin']['x'], d['frame']['origin']['y']))
        index = next(i for i, d in enumerate(displays) if d['uuid'] == current['uuid'])
        target = index + (1 if args[1] == 'next' else -1)
        if 0 <= target < len(displays):
            focus_display(displays[target]['uuid'])
        return
    if command == 'workspace':
        value = args[1]
        if value == 'recent':
            value = read_state('rift-previous-workspace.json')
            if value is None:
                return
        elif value in ('next', 'prev'):
            display, ws = current_slot()
            slots = sorted(mappings(read_state('display-layout.json') or display_plan()))
            current = ws['index'] + 1
            choices = [n for n in slots if n > current] if value == 'next' else [n for n in slots if n < current]
            if not choices:
                return
            value = min(choices) if value == 'next' else max(choices)
        switch(int(value)); return
    windows = snapshot()['windows']
    selected = next((w for w in windows if w['focused']), None)
    if command == 'previous-window':
        history = read_state('rift-focus.json', [])
        previous = next((w for h in reversed(history) for w in windows
                         if w['id'] == h['id'] and w['pid'] == h['pid'] and (not selected or w['id'] != selected['id'])), None)
        if previous:
            switch(previous['workspace']); focus_window(previous)
        return
    if selected is None:
        return
    if command == 'send':
        value = args[1]
        if value in ('next', 'prev'):
            slots = sorted(mappings(read_state('display-layout.json') or display_plan()))
            index = slots.index(selected['workspace']) + (1 if value == 'next' else -1)
            if not 0 <= index < len(slots):
                return
            value = slots[index]
        move_window(selected, int(value), '--follow' in args)
    elif command == 'display':
        displays = sorted(query('displays'), key=lambda d: (d['frame']['origin']['x'], d['frame']['origin']['y']))
        index = next(i for i, d in enumerate(displays) if d['uuid'] == selected['display'])
        target = displays[(index + (1 if args[1] == 'next' else -1)) % len(displays)]
        if '--focus' in args:
            focus_display(target['uuid'])
        else:
            plan = read_state('display-layout.json') or display_plan()
            owner = next(p for p in plan if p['uuid'] == target['uuid'])
            if owner['workspaces']:
                active = next((w['index']+1 for w in query('workspaces', target['space']) if w['is_active']), owner['workspaces'][0])
                move_window(selected, active if active in owner['workspaces'] else owner['workspaces'][0], True)
    elif command == 'float':
        from scripts.wm.rift_geometry import toggle_float
        toggle_float(sys.modules[__name__], selected)
    elif command == 'resize':
        delta = int(args[2])
        if selected['floating']:
            from scripts.wm.rift_geometry import set_frame
            frame = dict(selected['frame'])
            axis = 'w' if args[1] == 'width' else 'h'
            frame[axis] = max(100, frame[axis]+delta)
            set_frame(sys.modules[__name__], selected, frame)
            return
        if args[1] == 'width':
            from scripts.wm.rift_geometry import resize_width
            resize_width(sys.modules[__name__], selected, delta)
            return
        from scripts.wm.rift_geometry import resize_height
        resize_height(sys.modules[__name__], selected, delta)
    elif command == 'layout':
        _, ws = current_slot()
        execute('workspace', 'set-layout', 'stack' if ws['layout_mode'] != 'stack' else 'bsp')
    elif command == 'balance':
        # Rift has no balance command. Rebuild this workspace with default BSP splits.
        execute('workspace', 'set-layout', 'floating')
        execute('workspace', 'set-layout', 'bsp')
    elif command == 'preset':
        from scripts.wm.rift_geometry import preset
        preset(sys.modules[__name__], selected, windows, 1 if args[1] == 'up' else -1)
    elif command == 'insert':
        execute('layout', 'join-window', args[1])
    else:
        raise RuntimeError('Unknown Rift action: ' + command)


def main():
    command, *args = sys.argv[1:]
    if command in ('profile', 'release', 'action') and os.environ.get('DOTFILES_WM_LOCKED') != '1':
        # Use exactly the same descriptor-lock utility as wm.sh.
        shell = 'exec 9>"${TMPDIR:-/tmp}/.display-mode-state.lock"; lockf -s -t 10 9 || exit 1; export DOTFILES_WM_LOCKED=1; exec "$@"'
        sys.exit(subprocess.call(['/bin/bash', '-c', shell, 'rift-lock', sys.executable, str(Path(__file__).resolve()), command, *args]))
    if command == 'reload':
        sys.exit(subprocess.call(['/bin/bash', str(ROOT / 'wm.sh'), 'reload']))
    if command == 'snapshot':
        print(json.dumps(snapshot()))
    elif command == 'action':
        action(args)
    else:
        {'preflight': preflight, 'profile': profile, 'release': release, 'event': event, 'bar': bar}[command]()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        print('Rift: ' + str(error), file=sys.stderr)
        sys.exit(1)
