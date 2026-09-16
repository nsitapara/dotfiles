"""Use yabai's spatial policy with Rift's native window operations."""
import importlib.util
import json
from pathlib import Path
import sys
import time


def shared_module(filename):
    path = Path(__file__).resolve().parents[2] / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


geometry = shared_module('wm-direction.py')
sizes = shared_module('wm-size.py')
floats = shared_module('wm-float.py')


def set_frame(rift, window, frame):
    rift.focus_window(window)
    rift.run('/usr/bin/osascript', '-l', 'JavaScript',
             Path(__file__).with_name('set-focused-frame.js'),
             json.dumps(dict(id=window['id'], pid=window['pid'], frame=frame)))


def toggle_float(rift, selected):
    display, _ = rift.current_slot()
    screen = next(p for p in rift.read_state('display-layout.json') if p['uuid'] == display['uuid'])
    frame = rift.rect(display['frame'])
    area = dict(x=frame['x']+10, y=frame['y']+screen['top_padding'],
                w=frame['w']-20, h=frame['h']-screen['top_padding']-8)
    cache = rift.read_state('float-frames.json', {})
    key = str(selected['pid'])+':'+str(selected['id'])
    if selected['floating']:
        cache[key] = dict(frame=selected['frame'], area=area, at=time.time())
        rift.write_state('float-frames.json', dict(sorted(cache.items(), key=lambda item: item[1].get('at', 0))[-200:]))
        rift.execute('window', 'toggle-float')
    else:
        target = floats.restore_frame(cache.get(key), area)
        rift.execute('window', 'toggle-float')
        rift.wait_for(lambda: any(w['id'] == selected['id'] and w['floating'] for w in rift.snapshot()['windows']),
                      'Rift did not float the selected window')
        set_frame(rift, selected, target)


def directional(rift, direction, move=False):
    state = rift.snapshot()
    display, workspace = rift.current_slot()
    visible = [w for w in state['windows'] if w['visible']]
    selected = next((w for w in visible if w['focused']), None)
    screens = [dict(d, id=d['screen_id'], frame=rift.rect(d['frame'])) for d in state['displays']]
    source = next(d for d in screens if d['uuid'] == display['uuid'])
    local = [w for w in visible if w['display'] == display['uuid']]
    if move:
        if selected is None or selected['floating'] or workspace['layout_mode'] != 'bsp':
            return
        local = [w for w in local if not w['floating']]
    target = geometry.neighbor(selected, local, direction, allow_overlap=True) if selected else None
    if target:
        if move:
            rift.execute('layout', 'swap-windows', json.dumps(selected['rift_id']), json.dumps(target['rift_id']))
            rift.focus_window(selected)
        else:
            rift.focus_window(target)
        return
    if move and not geometry.spans_side(selected, local, direction):
        place_side(rift, selected, local, direction)
        return
    target_display = geometry.neighbor(source, screens, direction)
    if target_display is None:
        return
    if move:
        owner = next(p for p in rift.read_state('display-layout.json') if p['uuid'] == target_display['uuid'])
        slots = rift.query('workspaces', target_display['space'])
        number = next(w['index']+1 for w in slots if w['is_active'])
        if number not in owner['workspaces']:
            number = owner['workspaces'][0]
        rift.move_window(selected, number, True)
        arrived = rift.snapshot()['windows']
        selected = next(w for w in arrived if w['id'] == selected['id'])
        local = [w for w in arrived if w['display'] == selected['display']
                 and w['workspace'] == selected['workspace'] and not w['floating']]
        place_side(rift, selected, local, {'left':'right','right':'left','up':'down','down':'up'}[direction])
    else:
        target = geometry.entry_window([w for w in visible if w['display'] == target_display['uuid']],
                                       selected['frame'] if selected else source['frame'], direction)
        if target:
            rift.focus_window(target)
        else:
            rift.focus_display(target_display['uuid'])


def path_to_window(node, identity):
    if node.get('window_id') == identity:
        return [node]
    for child in node.get('children', []):
        path = path_to_window(child, identity)
        if path:
            return [node] + path
    return []


def place_side(rift, selected, windows, direction):
    """Create a root half without letting BSP's edge command cross displays.

    Rift's BSP MoveNode only swaps or crosses. Reinsert the other tiled leaves
    around the selected root using native float/tile, then set split orientation.
    Existing floating windows are never included.
    """
    if len(windows) < 2:
        return
    horizontal = direction in ('left', 'right')
    order = ('y','x') if horizontal else ('x','y')
    others = sorted((w for w in windows if w['id'] != selected['id']),
                    key=lambda w: tuple(w['frame'][a] for a in order))
    floated = []
    def tile(w):
        rift.focus_window(w)
        rift.execute('window', 'toggle-float')
        rift.wait_for(lambda: any(x['id'] == w['id'] and not x['floating'] for x in rift.snapshot()['windows']),
                      'Rift did not retile a window')
        floated.remove(w)
    def orientation(w, desired):
        rift.focus_window(w)
        tree = rift.query('layout')['container_tree']
        path = path_to_window(tree, w['rift_id'])
        if len(path) > 1 and path[-2]['layout_kind'] != desired:
            rift.execute('layout','toggle-orientation')
    try:
        for w in others:
            rift.focus_window(w)
            rift.execute('window','toggle-float')
            floated.append(w)
            rift.wait_for(lambda: any(x['id'] == w['id'] and x['floating'] for x in rift.snapshot()['windows']),
                          'Rift did not detach a window for rearrangement')
        rift.focus_window(selected)
        anchor = others[0]
        tile(anchor)
        orientation(selected, 'horizontal' if horizontal else 'vertical')
        if direction in ('right','down'):
            rift.execute('layout','swap-windows',json.dumps(selected['rift_id']),json.dumps(anchor['rift_id']))
        for w in others[1:]:
            rift.focus_window(anchor)
            tile(w)
            orientation(w, 'vertical' if horizontal else 'horizontal')
            anchor = w
    finally:
        original_error = sys.exc_info()[1]
        recovery_errors = []
        for w in list(floated):
            try:
                # A timed-out retile may actually have completed. Never toggle
                # it back to floating; skip windows that closed during the move.
                current = next((x for x in rift.snapshot()['windows'] if x['id'] == w['id']), None)
                if current and current['floating']:
                    tile(w)
            except (RuntimeError, ValueError, KeyError) as error:
                recovery_errors.append(str(error))
        try:
            rift.focus_window(selected)
        except (RuntimeError, ValueError, KeyError) as error:
            recovery_errors.append(str(error))
        if recovery_errors:
            message = 'Rift rearrangement recovery: ' + '; '.join(recovery_errors)
            if original_error is not None:
                print(message, file=sys.stderr)
            else:
                raise RuntimeError(message)
    rift.wait_for(lambda: geometry.spans_side(
        next(w for w in rift.snapshot()['windows'] if w['id'] == selected['id']),
        [w for w in rift.snapshot()['windows'] if w['id'] in {x['id'] for x in windows}], direction),
        'Rift did not expand the selected window into a full side')


def resize_width(rift, selected, delta):
    if selected['floating']:
        return
    display, workspace = rift.current_slot()
    if workspace['layout_mode'] != 'bsp':
        return
    # BSP applies half the requested amount to the nearest matching split ratio.
    # Use its parent frame so nested columns resize by the same pixel amount.
    tree = rift.query('layout')['container_tree']
    path = path_to_window(tree, selected['rift_id'])
    parent = next((node for node in reversed(path[:-1]) if node['layout_kind'] == 'horizontal'), None)
    if parent is None or any(n.get('is_fullscreen') or n.get('is_fullscreen_within_gaps') for n in path):
        return
    width = rift.rect(parent['frame'])['w'] - 15
    rift.execute('window', 'resize-by', '--amount=' + str(2 * delta / width))


def resize_height(rift, selected, delta):
    tree = rift.query('layout')['container_tree']
    path = path_to_window(tree, selected['rift_id'])
    if any(n.get('is_fullscreen') or n.get('is_fullscreen_within_gaps') for n in path):
        return
    pair = next(((parent, child) for parent, child in reversed(list(zip(path, path[1:])))
                 if parent['layout_kind'] == 'vertical'), None)
    if pair is None:
        return
    parent, child = pair
    frame = dict(selected['frame'])
    frame['h'] = max(100, frame['h']+delta)
    if parent['children'][0]['node_id'] != child['node_id']:
        frame['y'] -= delta
    # Rift observes AX resizing like a mouse resize and updates the split ratio.
    # Its CLI only exposes fixed 5% steps for vertical changes.
    set_frame(rift, selected, frame)


def preset(rift, selected, windows, step):
    display, workspace = rift.current_slot()
    if selected['floating'] or workspace['layout_mode'] != 'bsp':
        return
    local = [w for w in windows if w['display'] == selected['display']
             and w['space'] == selected['space'] and w['workspace'] == selected['workspace'] and not w['floating']]
    frame = rift.rect(display['frame'])
    plan = sizes.resize_plan(selected, local, step, gap=15, right_edge=frame['x']+frame['w']-10)
    if plan:
        resize_width(rift, selected, plan[1])
