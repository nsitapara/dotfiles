#!/usr/bin/env python3
"""Swap a tiled neighbor, fill the edge, then cross to an adjacent monitor."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wm_client import run

DIRECTIONS = {'left': 'west', 'right': 'east', 'up': 'north', 'down': 'south'}
OPPOSITE = {'north': 'south', 'south': 'north', 'west': 'east', 'east': 'west'}
AS_FORMAT = '%{window-id} %{workspace} %{window-layout} %{window-is-fullscreen} %{monitor-id}'


def query(*args):
    return json.loads(run('yabai', '-m', 'query', *args).stdout)


def window(id, *args):
    return run('yabai', '-m', 'window', id, *args)


def eligible(w):
    # Space queries include non-AX windows with is-floating=false. They are
    # not controllable BSP leaves (for example Activity Monitor's helper window).
    if any(w.get(key, True) is False for key in ('has-ax-reference', 'can-move', 'root-window')):
        return False
    return not any(w.get(key, False) for key in (
        'is-floating', 'is-minimized', 'is-hidden', 'is-sticky',
        'is-native-fullscreen', 'has-fullscreen-zoom', 'has-parent-zoom'))


def neighbor(selected, windows, direction, allow_overlap=False):
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
        forward = (g[axis]+g[size]/2-f[axis]-f[size]/2) * (1 if positive else -1)
        # Applications can refuse a tile's size and overlap the next tile.
        # Their centers still identify the direction; don't make them unreachable.
        if overlap > 1 and (distance >= -1 or (allow_overlap and forward > 1)):
            center = abs(f[cross]+f[extent]/2-g[cross]-g[extent]/2)
            candidates.append((max(0, distance), center, w['id'], w))
    return min(candidates, key=lambda c: c[:3])[-1] if candidates else None


def spans_side(selected, windows, direction):
    axis, size = ('y', 'h') if direction in ('left', 'right') else ('x', 'w')
    low = min(w['frame'][axis] for w in windows)
    high = max(w['frame'][axis]+w['frame'][size] for w in windows)
    f = selected['frame']
    return abs(f[axis]-low) <= 2 and abs(f[axis]+f[size]-high) <= 2


def entry_window(windows, source_frame, direction):
    """Enter from the near edge, preferring the same row or column."""
    axis, size, cross, extent = ('x','w','y','h') if direction in ('left','right') else ('y','h','x','w')
    def rank(w):
        f = w['frame']
        edge = f[axis] if direction in ('right','down') else -(f[axis]+f[size])
        center = abs(f[cross]+f[extent]/2-source_frame[cross]-source_frame[extent]/2)
        return edge, center, w['id']
    return min(windows, key=rank) if windows else None


def arrived_yabai_window(id, destination):
    for _ in range(25):
        arrived = query('--windows', '--window', id)
        windows = [w for w in query('--windows', '--space', destination['index']) if eligible(w)]
        if (arrived['display'] == destination['display'] and arrived['space'] == destination['index']
                and id in {w['id'] for w in windows}):
            return arrived, windows
        time.sleep(0.04)
    raise RuntimeError('Window has not arrived on the destination display; stopped.')


def cross_yabai(selected, direction):
    displays = query('--displays')
    source = next((d for d in displays if d['index'] == selected['display']), None)
    if source is None:
        return
    target = neighbor(source, displays, direction)
    if target is None:
        return
    spaces = query('--spaces', '--display', target['index'])
    # A native fullscreen Space cannot accept another tiled window.
    if not any(s['is-visible'] and not s.get('is-native-fullscreen')
               and s['type'] != 'fullscreen' for s in spaces):
        return
    destination = next(s for s in spaces if s['is-visible'])
    candidates = [w for w in query('--windows', '--space', destination['index']) if eligible(w)]
    if destination['type'] != 'bsp' or any(w.get('stack-index') for w in candidates):
        return
    incoming = {'left':'right','right':'left','up':'down','down':'up'}[direction]
    anchor = entry_window(candidates, selected['frame'], direction)
    hint = arrival_hint(anchor, candidates, incoming, selected['frame'])
    try:
        # Choose the incoming edge before sending the window. Otherwise yabai's
        # default second-child insertion visibly places it on the wrong side.
        if anchor:
            insert(anchor['id'], hint)
        window(selected['id'], '--display', target['index'])
    except RuntimeError:
        if anchor:
            clear_insert(anchor['id'], hint)
        raise
    # Follow immediately, before any fallible layout work. Otherwise a failed
    # warp leaves keyboard focus behind on the source monitor.
    run('yabai', '-m', 'window', '--focus', selected['id'])
    # Split the whole tiling area, not an already-small edge tile. The latter
    # creates quarter-width columns that apps with minimum widths overlap.
    arrived, windows = arrived_yabai_window(selected['id'], dict(destination,display=target['index']))
    place_yabai_side(arrived, windows, incoming)


def arrival_hint(anchor, windows, incoming, source_frame):
    if anchor and len(windows) in (2, 3):
        plan = side_plan(anchor, [anchor] + [w for w in windows if w['id'] != anchor['id']], incoming)
        if plan is not None and not plan[0]:
            # Split a full-side leaf across the other axis. With two residents
            # promotion reuses three slots; with three it creates a grid that
            # needs only one warp. Avoid introducing an extra narrow column.
            axis, size = ('y', 'h') if incoming in ('left', 'right') else ('x', 'w')
            f = anchor['frame']
            first = source_frame[axis] + source_frame[size]/2 <= f[axis] + f[size]/2
            return ('north' if first else 'south') if axis == 'y' else ('west' if first else 'east')
    return DIRECTIONS[incoming]


def focus_yabai(direction):
    displays = query('--displays')
    source = next((d for d in displays if d.get('has-focus')), None)
    if source is None:
        return
    windows = [w for w in query('--windows') if w.get('is-visible')
               and not w.get('is-minimized') and not w.get('is-hidden')]
    selected = next((w for w in windows if w.get('has-focus') and w['display'] == source['index']), None)
    if selected:
        local = [w for w in windows if w['display'] == source['index'] and w['space'] == selected['space']]
        target_window = neighbor(selected, local, direction, allow_overlap=True)
        if target_window:
            run('yabai', '-m', 'window', '--focus', target_window['id'])
            return
    target = neighbor(source, displays, direction)
    if target is None:
        return
    target_window = entry_window([w for w in windows if w['display'] == target['index']],
                                 selected['frame'] if selected else source['frame'], direction)
    if target_window:
        run('yabai', '-m', 'window', '--focus', target_window['id'])
    else:
        run('yabai', '-m', 'display', '--focus', target['index'])


def desktop_geometry():
    # AeroSpace doesn't expose frames. CoreGraphics provides bounds without
    # activating apps, reading window contents, or needing yabai to be running.
    script = '''
ObjC.import('AppKit'); ObjC.import('CoreGraphics');
var rows = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(0, 0)));
var windows = rows.map(function(w) {
    var f = w.kCGWindowBounds;
    return {id:w.kCGWindowNumber, frame:{x:f.X,y:f.Y,w:f.Width,h:f.Height}};
});
var displays = [], screens = $.NSScreen.screens;
for (var i=0; i<screens.count; i++) {
    var id = ObjC.unwrap(screens.objectAtIndex(i).deviceDescription.objectForKey('NSScreenNumber'));
    var f = $.CGDisplayBounds(id);
    displays.push({id:id,frame:{x:f.origin.x,y:f.origin.y,w:f.size.width,h:f.size.height}});
}
JSON.stringify({windows:windows,displays:displays});
'''
    return json.loads(run('/usr/bin/osascript', '-l', 'JavaScript', '-e', script).stdout)


def aerospace_tiled(w):
    return (w['window-layout'] in ('h_tiles', 'v_tiles', 'h_accordion', 'v_accordion')
            and str(w['window-is-fullscreen']).lower() != 'true')


def aerospace_monitor_target(monitor_id, direction, geometry):
    rows = json.loads(run('aerospace', 'list-monitors', '--json', '--format',
                         '%{monitor-id} %{monitor-appkit-nsscreen-screens-id}').stdout)
    frames = {d['id']: d['frame'] for d in geometry['displays']}
    displays = [dict(id=m['monitor-id'], frame=frames[m['monitor-appkit-nsscreen-screens-id']])
                for m in rows]
    source = next((d for d in displays if d['id'] == monitor_id), None)
    if source is None:
        return
    return neighbor(source, displays, direction)


def cross_aerospace(selected, direction, geometry):
    target = aerospace_monitor_target(selected['monitor-id'], direction, geometry)
    if target:
        # The directional form inserts at the incoming edge of the root layout.
        run('aerospace', 'move-node-to-monitor', '--window-id', selected['window-id'],
            '--focus-follows-window', direction)
        # Lift the root-level arrival onto its own side, with existing windows
        # grouped opposite it, matching yabai and avoiding narrow columns.
        opposite = {'left':'right','right':'left','up':'down','down':'up'}[direction]
        run('aerospace', 'move', '--window-id', selected['window-id'],
            '--boundaries', 'workspace', '--boundaries-action', 'create-implicit-container',
            '--fail-if-fullscreen', '--fail-if-macos-native-fullscreen', opposite)


def focus_aerospace(direction):
    rows = json.loads(run('aerospace', 'list-windows', '--focused', '--json', '--format', AS_FORMAT).stdout)
    selected = rows[0] if rows else None
    if selected:
        result = run('aerospace', 'focus', '--boundaries', 'workspace',
                     '--boundaries-action', 'fail', direction, check=False)
        if result.returncode == 0:
            return
        if result.stderr.strip():
            raise RuntimeError(result.stderr.strip())
    geometry = desktop_geometry()
    if selected:
        monitor_id = selected['monitor-id']
    else:
        monitors = json.loads(run('aerospace', 'list-monitors', '--focused', '--json', '--format', '%{monitor-id}').stdout)
        if not monitors:
            return
        monitor_id = monitors[0]['monitor-id']
    target = aerospace_monitor_target(monitor_id, direction, geometry)
    if not target:
        return
    spaces = json.loads(run('aerospace', 'list-workspaces', '--monitor', target['id'],
                            '--visible', '--json', '--format', '%{workspace}').stdout)
    if not spaces:
        return
    rows = json.loads(run('aerospace', 'list-windows', '--workspace', spaces[0]['workspace'],
                          '--json', '--format', AS_FORMAT).stdout)
    frames = {w['id']: w['frame'] for w in geometry['windows']}
    windows = [dict(id=w['window-id'], frame=frames[w['window-id']]) for w in rows]
    origin = frames[selected['window-id']] if selected else target['frame']
    candidate = entry_window(windows, origin, direction)
    if candidate:
        run('aerospace', 'focus', '--window-id', candidate['id'])
    else:
        run('aerospace', 'focus-monitor', str(target['id']))


def insert(id, direction):
    # --insert toggles an existing identical hint off. Set a different hint first.
    # Both hints use one native request, avoiding an extra IPC round trip.
    window(id, '--insert', OPPOSITE[direction], '--insert', direction)


def clear_insert(id, direction):
    # Force a known hint, then toggle off; also safe if a move consumed it.
    try:
        insert(id, direction)
        window(id, '--insert', direction)
    except RuntimeError:
        pass  # The anchor may have closed too. Preserve the original error.


def warp_at(id, anchor, direction):
    try:
        insert(anchor, direction)
        window(id, '--warp', anchor)
    except RuntimeError:
        clear_insert(anchor, direction)
        raise


def settled_windows(space, ids):
    # macOS sends frame updates after yabai acknowledges a layout command.
    # Wait for stable frames before deriving another action.
    previous = None
    stable_samples = 0
    for _ in range(25):
        time.sleep(0.04)
        windows = [w for w in query('--windows', '--space', space) if w['id'] in ids]
        if {w['id'] for w in windows} != ids:
            raise RuntimeError('Windows changed during rearrangement; stopped.')
        overlap = False
        coincident = False
        for i, a in enumerate(windows):
            f = a['frame']
            for b in windows[i+1:]:
                g = b['frame']
                if abs(f['x']-g['x']) <= 2 and abs(f['y']-g['y']) <= 2:
                    coincident = True
                if (min(f['x']+f['w'],g['x']+g['w'])-max(f['x'],g['x']) > 2 and
                        min(f['y']+f['h'],g['y']+g['h'])-max(f['y'],g['y']) > 2):
                    overlap = True
        snapshot = sorted((w['id'], tuple(w['frame'][a] for a in ('x','y','w','h'))) for w in windows)
        stable_samples = stable_samples + 1 if snapshot == previous else 1
        if not overlap and snapshot == previous:
            return windows
        # App minimum sizes can leave settled tiles overlapping. Distinct,
        # stable origins still let us restore their reading order safely.
        if overlap and not coincident and stable_samples >= 4:
            return windows
        previous = snapshot
    raise RuntimeError('Window frames have not settled; stopped.')


def wait_for_frames(space, expected):
    """Wait for the requested frames, allowing stable minimum-size clamping."""
    deadline = time.monotonic() + 1
    previous = None
    stable_since = None
    while True:
        windows = [w for w in query('--windows', '--space', space) if w['id'] in expected]
        if {w['id'] for w in windows} != set(expected):
            raise RuntimeError('Windows changed during rearrangement; stopped.')
        if all(abs(w['frame'][axis] - expected[w['id']][axis]) <= 2
               for w in windows for axis in ('x','y','w','h')):
            return windows
        now = time.monotonic()
        # Origins must match. Sizes were estimated from the previous occupants:
        # swapping a minimum-sized app out can also make its replacement smaller.
        # Require stable actual frames instead of waiting for those estimates.
        positions_match = all(
            all(abs(w['frame'][a] - expected[w['id']][a]) <= 2 for a in ('x', 'y'))
            for w in windows
        )
        snapshot = sorted((w['id'], tuple(w['frame'][a] for a in ('x','y','w','h'))) for w in windows)
        if not positions_match:
            stable_since = None
        elif snapshot != previous or stable_since is None:
            stable_since = now
        elif now - stable_since >= 0.1:
            return windows
        previous = snapshot
        if now >= deadline:
            raise RuntimeError('Requested window frames have not arrived; stopped.')
        time.sleep(0.005)


def side_plan(selected, windows, direction):
    """Reuse an existing two-column/row layout instead of rebuilding its tree."""
    if len(windows) < 2:
        return None
    axis, size, cross, extent = ('x','w','y','h') if direction in ('left','right') else ('y','h','x','w')
    low = {a:min(w['frame'][a] for w in windows) for a in ('x','y')}
    high = {a:max(w['frame'][a]+w['frame'][s] for w in windows) for a,s in [('x','w'),('y','h')]}
    order = (cross, axis)
    desired_others = sorted((w for w in windows if w['id'] != selected['id']),
                            key=lambda w: tuple(w['frame'][a] for a in order))
    for root in windows:
        group = [w for w in windows if w['id'] != root['id']]
        f, g = root['frame'], group[0]['frame']
        if not spans_side(root,windows,direction) or abs(f[size]-g[size]) > 2:
            continue
        if not all(abs(w['frame'][axis]-g[axis]) <= 2 and abs(w['frame'][size]-g[size]) <= 2
                   and abs(w['frame'][extent]-g[extent]) <= 2 for w in group):
            continue
        # Reject overlaps/minimum-size clamping and layouts with extra columns.
        if not (f[axis]+f[size] <= g[axis]+2 or g[axis]+g[size] <= f[axis]+2):
            continue
        ordered = sorted(group,key=lambda w:w['frame'][cross])
        if any(a['frame'][cross]+a['frame'][extent] > b['frame'][cross]+2
               for a,b in zip(ordered,ordered[1:])):
            continue
        correct_side = (abs(f[axis]-low[axis]) <= 2 if direction in ('left','up')
                        else abs(f[axis]+f[size]-high[axis]) <= 2)
        plans = []
        for transform in ([None] if correct_side else ['mirror','rotate']):
            frames = {w['id']:dict(w['frame']) for w in windows}
            commands = []
            if transform:
                for frame in frames.values():
                    frame[axis] = low[axis]+high[axis]-frame[axis]-frame[size]
                    if transform == 'rotate':
                        frame[cross] = low[cross]+high[cross]-frame[cross]-frame[extent]
                commands.append(('space',selected['space'],'--mirror','y-axis' if axis=='x' else 'x-axis')
                                if transform == 'mirror' else ('space',selected['space'],'--rotate','180'))
            slots = [root['id']] + sorted((w['id'] for w in group),key=lambda id:tuple(frames[id][a] for a in order))
            wanted = [selected['id']] + [w['id'] for w in desired_others]
            occupants = list(slots)
            for i,id in enumerate(wanted):
                if occupants[i] != id:
                    j = occupants.index(id)
                    commands.append(('window',id,'--swap',occupants[i]))
                    occupants[i],occupants[j] = occupants[j],occupants[i]
            expected = {id:frames[slot] for id,slot in zip(wanted,slots)}
            plans.append((commands,expected))
        return min(plans,key=lambda plan:len(plan[0]))
    return None


def grid_promotion(selected, windows, direction):
    """Find the one leaf to move out of a selected half of a 2x2 BSP grid."""
    if len(windows) != 4:
        return None
    horizontal = direction in ('left', 'right')
    axis,size,cross,extent = ('x','w','y','h') if horizontal else ('y','h','x','w')
    # Identical geometry can represent a row-rooted or column-rooted tree.
    # Require the actual parent split; geometry alone cannot justify this warp.
    split = 'horizontal' if horizontal else 'vertical'
    if any(w.get('split-type') != split or not eligible(w) or w.get('stack-index') for w in windows):
        return None
    f = selected['frame']
    if any(abs(w['frame'][key]-f[key]) > 2 for w in windows for key in (size,extent)):
        return None
    local = [w for w in windows if abs(w['frame'][axis]-f[axis]) <= 2]
    opposite = [w for w in windows if w not in local]
    if len(local) != 2 or len(opposite) != 2:
        return None
    local.sort(key=lambda w:w['frame'][cross])
    opposite.sort(key=lambda w:w['frame'][cross])
    g = opposite[0]['frame']
    if abs(opposite[1]['frame'][axis]-g[axis]) > 2:
        return None
    if not (f[axis]+f[size] <= g[axis]+2 if direction in ('left','up')
            else g[axis]+g[size] <= f[axis]+2):
        return None
    if local[0]['frame'][cross]+f[extent] > local[1]['frame'][cross]+2:
        return None
    if any(abs(a['frame'][cross]-b['frame'][cross]) > 2 for a,b in zip(local,opposite)):
        return None
    displaced = next(w for w in local if w['id'] != selected['id'])
    others = sorted((w for w in windows if w['id'] != selected['id']),
                    key=lambda w:(w['frame'][cross],w['frame'][axis]))
    index = others.index(displaced)
    first = displaced['id'] == local[0]['id']
    anchor = others[index+1] if first and index+1 < len(others) else others[max(0,index-1)]
    before = index < others.index(anchor)
    hint = ('north' if before else 'south') if horizontal else ('west' if before else 'east')
    return displaced,anchor,hint


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
    if not windows or any(w.get('stack-index', 0) for w in windows):
        return
    target = neighbor(selected, windows, direction, allow_overlap=True)
    if target:
        window(id, '--swap', target['id'])
        expected = {w['id']:w['frame'] for w in windows}
        expected[id],expected[target['id']] = expected[target['id']],expected[id]
        wait_for_frames(selected['space'], expected)
        return
    if spans_side(selected, windows, direction):
        cross_yabai(selected, direction)
        return
    place_yabai_side(selected, windows, direction)


def place_yabai_side(selected, windows, direction):
    """Give this window a root-level side, even if it already spans a narrow column."""
    if len(windows) < 2:
        return
    plan = side_plan(selected, windows, direction)
    if plan is not None:
        commands,expected = plan
        for command in commands:
            run('yabai','-m',*command)
        if commands:
            wait_for_frames(selected['space'],expected)
        return
    id = selected['id']

    horizontal = direction in ('left', 'right')
    order = ('y', 'x') if horizontal else ('x', 'y')
    others = sorted((w for w in windows if w['id'] != id),
                    key=lambda w: tuple(w['frame'][a] for a in order))
    grid = grid_promotion(selected, windows, direction)
    if grid:
        displaced,anchor,hint = grid
        warp_at(displaced['id'], anchor['id'], hint)
        # Balance the three remaining leaves along their column/row. The root
        # half is already correct, so don't shrink and re-expand the selection.
        run('yabai', '-m', 'space', selected['space'], '--balance', 'x-axis' if horizontal else 'y-axis')
        restore_order(selected, windows, others, order)
        return
    anchor = others[0]['id']
    # Gather every other leaf beside the anchor. The selected leaf is never
    # removed, floated, or sent to another Space. It becomes a root-level tile.
    for other in others[1:]:
        warp_at(other['id'], anchor, 'south' if horizontal else 'east')
    current = query('--windows', '--window', id)
    desired_split = 'vertical' if horizontal else 'horizontal'
    if current['split-type'] != desired_split:
        window(id, '--toggle', 'split')
    current = query('--windows', '--window', id)
    desired_child = 'first_child' if direction in ('left', 'up') else 'second_child'
    if current['split-child'] != desired_child:
        run('yabai', '-m', 'space', selected['space'], '--mirror', 'y-axis' if horizontal else 'x-axis')
    # Repeated warps make an uneven chain (1/2, 1/4, 1/8 ...). Give the
    # grouped windows equal room before setting the selected side's ratio.
    run('yabai', '-m', 'space', selected['space'], '--balance')
    window(id, '--ratio', 'abs:0.5')
    restore_order(selected, windows, others, order)


def restore_order(selected, windows, others, order):
    # Natural warp chooses the nearest half. Restore the other apps' reading order
    # with swaps, which preserve the new geometry and keep focus on the selection.
    fresh = settled_windows(selected['space'], {w['id'] for w in windows})
    other_ids = {w['id'] for w in others}
    slots = sorted((w for w in fresh if w['id'] in other_ids),
                   key=lambda w: tuple(w['frame'][a] for a in order))
    ids = [w['id'] for w in slots]
    reordered = False
    for i, desired in enumerate(w['id'] for w in others):
        if ids[i] != desired:
            j = ids.index(desired)
            window(desired, '--swap', ids[i])
            reordered = True
            ids[i], ids[j] = ids[j], ids[i]
    if reordered:
        settled_windows(selected['space'], {w['id'] for w in windows})


def aerospace(direction, id=None):
    rows = json.loads(run('aerospace', 'list-windows', '--all' if id else '--focused', '--json',
                          '--format', AS_FORMAT).stdout)
    if id:
        rows = [w for w in rows if w['window-id'] == id]
    if not rows:
        return
    selected = rows[0]
    id = id or selected['window-id']
    if not aerospace_tiled(selected):
        return
    result = run('aerospace', 'swap', '--window-id', id, direction, check=False)
    if result.returncode == 0:
        return
    # A real command failure is not evidence that we reached an edge.
    if result.stderr.strip():
        raise RuntimeError(result.stderr.strip())
    workspace = selected['workspace']
    rows = json.loads(run('aerospace', 'list-windows', '--workspace', workspace,
                          '--json', '--format', AS_FORMAT).stdout)
    geometry = desktop_geometry()
    frames = {w['id']: w['frame'] for w in geometry['windows']}
    windows = [dict(id=w['window-id'], frame=frames[w['window-id']])
               for w in rows if aerospace_tiled(w)]
    if not windows or id not in {w['id'] for w in windows}:
        return
    if spans_side(dict(frame=frames[id]), windows, direction):
        cross_aerospace(selected, direction, geometry)
        return
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
    parser.add_argument('--focus', action='store_true', help='Change focus without moving windows')
    args = parser.parse_args()
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    state = Path.home()/'.local/state/dotfiles-wm'
    state.mkdir(parents=True, exist_ok=True)
    # Layout changes may wait for app geometry, especially at minimum sizes.
    # Keep focus independent so those waits never discard Cmd+arrow presses.
    lock_name = 'focus.lock' if args.focus else 'direction.lock'
    with (state/lock_name).open('w') as lock:
        try:
            # Drop overlapping requests of the same kind, never queue repeats.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            if args.focus:
                if args.manager == 'yabai':
                    focus_yabai(args.direction)
                else:
                    focus_aerospace(args.direction)
            else:
                (yabai if args.manager == 'yabai' else aerospace)(args.direction, args.window_id)
        except (RuntimeError, ValueError, KeyError) as error:
            print('Window move: ' + str(error), file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
