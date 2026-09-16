"""Directional movement swaps, fills a side, then crosses without wrapping."""
import importlib.util
import fcntl
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('direction', ROOT/'wm-direction.py')
wm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wm)


def w(id, x, y, width, height, **extra):
    return dict(id=id, space=1, display=1, frame=dict(x=x,y=y,w=width,h=height), **extra)


class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.windows = [w(1,0,0,500,1000),w(2,510,0,500,495),w(3,510,505,500,495)]

    def test_non_ax_window_is_not_a_tiled_neighbor_or_resize_candidate(self):
        # Real query shape: Activity Monitor lists this window, but commands
        # addressed to its ID fail with "could not locate window".
        ghost = w(44041,510,0,1728,1085, **{'has-ax-reference':False,
                  'can-move':False, 'is-floating':False, 'is-visible':False})
        self.assertFalse(wm.eligible(ghost))
        for key in ['has-ax-reference', 'can-move', 'root-window']:
            self.assertFalse(wm.eligible(dict(self.windows[0], **{key:False})))
        with patch.object(wm,'query',side_effect=[self.windows[0],{'type':'bsp'},
                [self.windows[0],ghost]]), patch.object(wm,'cross_yabai') as cross, \
                patch.object(wm,'window') as command:
            wm.yabai('right')
        cross.assert_called_once_with(self.windows[0],'right')
        command.assert_not_called()

    def test_failed_destination_layout_keeps_focus_on_moved_window(self):
        displays = [dict(w(10,0,0,1010,1000),index=1),
                    dict(w(20,1010,0,1010,1000),index=2)]
        selected = self.windows[0]
        arrived = dict(selected,space=4,display=2)
        events = []
        def place(*args):
            events.append(('layout',args[-1]))
            raise RuntimeError('window closed during warp')
        with patch.object(wm,'query',side_effect=[displays,
                [{'index':4,'is-visible':True,'type':'bsp'}],[],arrived,[arrived]]), \
                patch.object(wm,'window',side_effect=lambda *a:events.append(a)), \
                patch.object(wm,'run',side_effect=lambda *a:events.append(a)), \
                patch.object(wm,'place_yabai_side',side_effect=place):
            with self.assertRaisesRegex(RuntimeError,'closed during warp'):
                wm.cross_yabai(selected,'right')
        self.assertEqual(events,[(1,'--display',2),
            ('yabai','-m','window','--focus',1),('layout','left')])

    def test_warp_failure_clears_hint_even_if_it_was_already_consumed(self):
        for consumed in [False,True]:
            with self.subTest(consumed=consumed):
                hint = None
                def window(id,action,value):
                    nonlocal hint
                    if action == '--insert':
                        hint = None if hint == value else value
                    if action == '--warp':
                        if consumed:
                            hint = None
                        raise RuntimeError('warp failed')
                with patch.object(wm,'side_plan',return_value=None), \
                        patch.object(wm,'window',side_effect=window),patch.object(wm,'query') as query:
                    with self.assertRaisesRegex(RuntimeError,'warp failed'):
                        wm.place_yabai_side(self.windows[2],self.windows,'right')
                self.assertIsNone(hint)
                query.assert_not_called()

    def test_focus_runs_while_resize_or_move_is_busy_in_both_managers(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home/'.local/state/dotfiles-wm'
            state.mkdir(parents=True)
            with (state/'direction.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for manager in ['yabai', 'aerospace']:
                    with self.subTest(manager=manager), patch.object(wm.Path, 'home', return_value=home), \
                            patch.object(wm.sys, 'argv', ['wm-direction.py', manager, 'right', '--focus']), \
                            patch.object(wm, 'focus_'+manager) as focus:
                        wm.main()
                    focus.assert_called_once_with('right')

    def test_busy_moves_and_duplicate_focus_still_drop_without_waiting(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home/'.local/state/dotfiles-wm'
            state.mkdir(parents=True)
            for name, flags, function in [('direction.lock', [], 'yabai'),
                                           ('focus.lock', ['--focus'], 'focus_yabai')]:
                with (state/name).open('w') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with patch.object(wm.Path, 'home', return_value=home), \
                            patch.object(wm.sys, 'argv', ['wm-direction.py', 'yabai', 'right', *flags]), \
                            patch.object(wm, function) as action:
                        wm.main()
                    action.assert_not_called()

    def test_neighbors_and_edges_in_screenshot(self):
        a,b,c = self.windows
        self.assertEqual(wm.neighbor(c,self.windows,'left')['id'],1)
        self.assertEqual(wm.neighbor(c,self.windows,'up')['id'],2)
        self.assertIsNone(wm.neighbor(c,self.windows,'right'))
        self.assertIsNone(wm.neighbor(c,self.windows,'down'))
        self.assertFalse(wm.spans_side(c,self.windows,'right'))
        self.assertTrue(wm.spans_side(a,self.windows,'left'))

    def test_swap_does_not_warp_or_resize(self):
        def query(*args):
            if args[:2] == ('--spaces','--space'): return {'type':'bsp'}
            if args[:2] == ('--windows','--window'): return self.windows[2]
            return self.windows
        with patch.object(wm,'query',side_effect=query), patch.object(wm,'window') as command, patch.object(wm,'wait_for_frames'):
            wm.yabai('left')
        command.assert_called_once_with(3,'--swap',1)

    def test_outer_edge_full_side_is_noop(self):
        with patch.object(wm,'query',side_effect=[self.windows[0],{'type':'bsp'},self.windows,
                [dict(id=10,index=1,frame=dict(x=0,y=0,w=1010,h=1000))]]), patch.object(wm,'window') as command:
            wm.yabai('left')
        command.assert_not_called()

    def test_full_side_and_single_window_cross_immediately(self):
        displays = [dict(id=10,index=1,frame=dict(x=0,y=0,w=1010,h=1000)),
                    dict(id=20,index=2,frame=dict(x=-1010,y=0,w=1010,h=1000))]
        halves = [w(1,0,0,500,1000),w(2,510,0,500,1000)]
        for windows in [halves, self.windows, [self.windows[0]]]:
            arrived = dict(windows[0],display=2,space=4)
            with self.subTest(count=len(windows)), patch.object(wm,'query',side_effect=[
                    windows[0],{'type':'bsp'},windows,displays,[{'index':4,'is-visible':True,'type':'bsp'}],[],arrived,[arrived]]), patch.object(wm,'window') as command, patch.object(wm,'run') as run:
                wm.yabai('left')
            command.assert_called_once_with(1,'--display',2)
            self.assertEqual([c.args for c in run.call_args_list], [
                ('yabai','-m','window','--focus',1)])

    def test_native_fullscreen_destination_is_untouched(self):
        displays = [dict(id=10,index=1,frame=dict(x=0,y=0,w=1010,h=1000)),
                    dict(id=20,index=2,frame=dict(x=-1010,y=0,w=1010,h=1000))]
        with patch.object(wm,'query',side_effect=[displays,[{'is-visible':True,'type':'fullscreen'}]]), patch.object(wm,'window') as command:
            wm.cross_yabai(self.windows[0],'left')
        command.assert_not_called()

    def test_monitor_direction_uses_position_with_no_wrap(self):
        displays = [w(1,0,0,1000,1000),w(2,1000,200,1000,1000),w(3,0,-800,1000,800)]
        self.assertEqual(wm.neighbor(displays[0],displays,'right')['id'],2)
        self.assertEqual(wm.neighbor(displays[0],displays,'up')['id'],3)
        self.assertEqual(wm.neighbor(displays[2],displays,'down')['id'],1)
        self.assertIsNone(wm.neighbor(displays[1],displays,'right'))

    def test_incoming_edge_and_row_are_preferred(self):
        windows = [w(1,0,0,490,490), w(2,500,0,490,490),
                   w(3,0,500,490,490),w(4,500,500,490,490)]
        origin = dict(x=1100,y=500,w=490,h=490)
        self.assertEqual(wm.entry_window(windows,origin,'left')['id'],4)
        self.assertEqual(wm.entry_window(windows,origin,'right')['id'],3)
        origin = dict(x=500,y=1100,w=490,h=490)
        self.assertEqual(wm.entry_window(windows,origin,'up')['id'],4)
        self.assertEqual(wm.entry_window(windows,origin,'down')['id'],2)
        self.assertIsNone(wm.entry_window([],origin,'left'))

    def test_yabai_move_enters_near_edge(self):
        displays = [dict(id=10,index=1,frame=dict(x=1010,y=0,w=1010,h=1000)),
                    dict(id=20,index=2,frame=dict(x=0,y=0,w=1010,h=1000))]
        selected = w(8,1010,505,500,495)
        arrived = dict(selected,display=2,space=4)
        destination = self.windows+[arrived]
        with patch.object(wm,'query',side_effect=[displays,[{'index':4,'is-visible':True,'type':'bsp'}],self.windows,arrived,destination]), patch.object(wm,'window') as command, patch.object(wm,'run'), patch.object(wm,'place_yabai_side') as place:
            wm.cross_yabai(selected,'left')
        command.assert_called_once_with(8,'--display',2)
        place.assert_called_once_with(arrived,destination,'right')

    def test_yabai_focus_enters_near_edge_without_moving_windows(self):
        displays = [dict(id=10,index=1,frame=dict(x=1010,y=0,w=1010,h=1000),**{'has-focus':True}),
                    dict(id=20,index=2,frame=dict(x=0,y=0,w=1010,h=1000))]
        windows = [dict(w,display=2,**{'is-visible':True}) for w in self.windows]
        windows.append(w(8,1010,505,500,495,**{'has-focus':True,'is-visible':True}))
        with patch.object(wm,'query',side_effect=[displays,windows]),patch.object(wm,'run') as command:
            wm.focus_yabai('left')
        self.assertEqual([c.args for c in command.call_args_list],[
            ('yabai','-m','window','--focus',3)])

    def test_yabai_local_focus_and_empty_destination(self):
        displays = [dict(id=10,index=1,frame=dict(x=0,y=0,w=1010,h=1000),**{'has-focus':True}),
                    dict(id=20,index=2,frame=dict(x=1010,y=0,w=1010,h=1000))]
        windows = [dict(w,**{'is-visible':True,'has-focus':w['id']==3}) for w in self.windows]
        for direction, expected in [('left',[('yabai','-m','window','--focus',1)]),
                                    ('right',[('yabai','-m','display','--focus',2)]),('down',[])]:
            with self.subTest(direction=direction),patch.object(wm,'query',side_effect=[displays,windows]),patch.object(wm,'run') as command:
                wm.focus_yabai(direction)
            self.assertEqual([c.args for c in command.call_args_list],expected)

    def test_aerospace_focus_enters_right_edge_when_going_left(self):
        row = {'window-id':8,'workspace':'2','window-layout':'h_tiles','window-is-fullscreen':False,'monitor-id':2}
        geometry = {'windows':self.windows+[w(8,1100,505,500,495)]}
        calls = []
        def run(*args,**kwargs):
            calls.append(args)
            if args[1] == 'list-windows':
                rows = [dict(row,**{'window-id':w['id']}) for w in self.windows] if '--workspace' in args else [row]
                return SimpleNamespace(stdout=json.dumps(rows))
            if args[1] == 'list-workspaces': return SimpleNamespace(stdout='[{"workspace":"1"}]')
            return SimpleNamespace(returncode=1,stderr='')
        with patch.object(wm,'run',side_effect=run),patch.object(wm,'desktop_geometry',return_value=geometry),patch.object(wm,'aerospace_monitor_target',return_value={'id':1}):
            wm.focus_aerospace('left')
        self.assertEqual(calls[-1],('aerospace','focus','--window-id',3))
        self.assertFalse(any(c[1].startswith('move') for c in calls))

    def test_aerospace_arrival_gets_its_own_incoming_side(self):
        selected = {'window-id':8,'monitor-id':2}
        for direction, layout, incoming in [('left','v_tiles','right'),('right','v_tiles','left'),
                                            ('up','h_tiles','down'),('down','h_tiles','up')]:
            with self.subTest(direction=direction),patch.object(wm,'aerospace_monitor_target',return_value={'id':1}),patch.object(wm,'run',return_value=SimpleNamespace(stdout=layout)) as command:
                wm.cross_aerospace(selected,direction,{})
            self.assertEqual(command.call_args.args[-1],incoming)
            self.assertIn('create-implicit-container',command.call_args.args)

    def test_all_profiles_bind_focus_and_movement_to_shared_helper(self):
        import tomllib
        for profile in ['aerospace','aerospace-docked']:
            config = tomllib.loads((ROOT/profile/'.config/aerospace/aerospace.toml').read_text())
            bindings = config['mode']['main']['binding']
            for direction in wm.DIRECTIONS:
                self.assertIn(f'wm-direction.py" aerospace {direction} --focus', bindings[f'cmd-{direction}'])
                self.assertTrue(bindings[f'cmd-shift-{direction}'].endswith(f'aerospace {direction}'))
        skhd = (ROOT/'skhd/.config/skhd/skhdrc').read_text()
        for direction in wm.DIRECTIONS:
            self.assertIn(f'cmd - {direction} : /usr/bin/python3 "$HOME/dotfiles/wm-direction.py" yabai {direction} --focus',skhd)

    def test_floating_and_zoomed_windows_are_untouched(self):
        for flag in ['is-floating','is-native-fullscreen','has-fullscreen-zoom','is-minimized']:
            with self.subTest(flag=flag), patch.object(wm,'query',return_value=dict(self.windows[2],**{flag:True})), patch.object(wm,'window') as command:
                wm.yabai('right')
                command.assert_not_called()

    def test_existing_stacks_are_preserved(self):
        self.windows[1]['stack-index'] = 1
        with patch.object(wm,'query',side_effect=[self.windows[2],{'type':'bsp'},self.windows]), patch.object(wm,'window') as command:
            wm.yabai('right')
        command.assert_not_called()

    def test_edge_promotion_moves_other_leaf_and_preserves_selection(self):
        promoted = dict(self.windows[2], **{'split-type':'vertical','split-child':'second_child'})
        fresh = [w(1,0,0,500,495),w(2,0,505,500,495),w(3,510,0,500,1000)]
        with patch.object(wm,'query',side_effect=[self.windows[2],{'type':'bsp'},self.windows,promoted,promoted]), patch.object(wm,'window') as command, patch.object(wm,'run') as run, patch.object(wm,'settled_windows',return_value=fresh), patch.object(wm,'side_plan',return_value=None):
            wm.yabai('right')
        calls = [c.args for c in command.call_args_list]
        self.assertIn((2,'--warp',1),calls)
        self.assertIn((3,'--ratio','abs:0.5'),calls)
        self.assertFalse(any('--toggle' in c or '--space' in c for c in calls))
        run.assert_called_once_with('yabai','-m','space',1,'--balance')

    def test_minimum_width_overlap_does_not_hide_slack_from_focus(self):
        t3 = w(984,3209,50,840,1382,**{'has-focus':True,'is-visible':True})
        slack = w(3668,3848,50,1262,1382,**{'is-visible':True})
        chrome = w(11209,2570,50,623,1382,**{'is-visible':True})
        windows = [t3,slack,chrome]
        self.assertEqual(wm.neighbor(t3,windows,'right',allow_overlap=True)['id'],3668)
        self.assertEqual(wm.neighbor(slack,windows,'left',allow_overlap=True)['id'],984)
        displays = [dict(id=2,index=1,frame=dict(x=2560,y=0,w=2560,h=1440),**{'has-focus':True})]
        with patch.object(wm,'query',side_effect=[displays,windows]),patch.object(wm,'run') as run:
            wm.focus_yabai('right')
        run.assert_called_once_with('yabai','-m','window','--focus',3668)

    def test_move_waits_for_space_membership_before_rearranging(self):
        old = w(8,0,0,1000,1000)
        arrived = dict(old,space=4,display=2)
        with patch.object(wm,'query',side_effect=[old,[],arrived,[arrived]]),patch.object(wm.time,'sleep') as sleep:
            self.assertEqual(wm.arrived_yabai_window(8,{'index':4,'display':2}), (arrived,[arrived]))
        sleep.assert_called_once_with(.04)

    def test_narrow_full_height_arrival_is_rebuilt_and_balanced(self):
        selected = w(984,3209,50,840,1382,**{'split-type':'vertical','split-child':'first_child'})
        windows = [w(11209,2570,50,623,1382),selected,w(3668,3848,50,1262,1382)]
        fresh = [w(984,2570,50,1262,1382),w(11209,3848,50,1262,683),w(3668,3848,749,1262,683)]
        self.assertTrue(wm.spans_side(selected,windows,'left'))
        with patch.object(wm,'query',return_value=selected),patch.object(wm,'window') as window,patch.object(wm,'run') as run,patch.object(wm,'settled_windows',return_value=fresh):
            wm.place_yabai_side(selected,windows,'left')
        self.assertIn((3668,'--warp',11209),[c.args for c in window.call_args_list])
        self.assertIn((984,'--ratio','abs:0.5'),[c.args for c in window.call_args_list])
        run.assert_called_once_with('yabai','-m','space',1,'--balance')

    def test_three_window_promotion_reuses_tiles_with_two_changes(self):
        commands, expected = wm.side_plan(self.windows[2],self.windows,'right')
        self.assertEqual(len(commands),2)
        self.assertEqual(expected[3],dict(x=510,y=0,w=500,h=1000))
        self.assertEqual(expected[1],dict(x=0,y=0,w=500,h=495))
        self.assertEqual(expected[2],dict(x=0,y=505,w=500,h=495))
        with patch.object(wm,'run') as run,patch.object(wm,'wait_for_frames') as wait,patch.object(wm,'settled_windows') as slow:
            wm.place_yabai_side(self.windows[2],self.windows,'right')
        self.assertEqual(run.call_count,2)
        wait.assert_called_once_with(1,expected)
        slow.assert_not_called()

    def test_side_plans_preserve_geometry_and_reading_order_all_directions(self):
        for transpose in [False,True]:
            windows = self.windows if not transpose else [dict(w,frame=dict(x=w['frame']['y'],y=w['frame']['x'],w=w['frame']['h'],h=w['frame']['w'])) for w in self.windows]
            for direction in (['left','right'] if not transpose else ['up','down']):
                for selected in windows:
                    commands,expected = wm.side_plan(selected,windows,direction)
                    frames = {w['id']:dict(w['frame']) for w in windows}
                    for command in commands:
                        if command[0]=='window':
                            a,b=command[1],command[3];frames[a],frames[b]=frames[b],frames[a]
                        else:
                            axes = [('x','w',1010),('y','h',1000)] if not transpose else [('x','w',1000),('y','h',1010)]
                            for f in frames.values():
                                for axis,size,total in axes:
                                    if command[2]=='--rotate' or (axis=='x')==(command[3]=='y-axis'):
                                        f[axis]=total-f[axis]-f[size]
                    self.assertEqual(frames,expected)
                    axis,size,cross,extent=('x','w','y','h') if not transpose else ('y','h','x','w')
                    self.assertEqual(expected[selected['id']][axis],0 if direction in ('left','up') else 510)
                    self.assertEqual(expected[selected['id']][extent],1000)
                    before=sorted((w for w in windows if w['id']!=selected['id']),key=lambda w:(w['frame'][cross],w['frame'][axis]))
                    after=sorted((id for id in expected if id!=selected['id']),key=lambda id:expected[id][cross])
                    self.assertEqual(after,[w['id'] for w in before])

    def test_correct_side_is_a_noop_and_unequal_or_overlapping_tiles_use_fallback(self):
        commands,_=wm.side_plan(self.windows[0],self.windows,'left')
        self.assertEqual(commands,[])
        bad=[dict(w,frame=dict(w['frame'])) for w in self.windows]
        bad[1]['frame']['h']=600
        self.assertIsNone(wm.side_plan(bad[2],bad,'right'))

    def test_wait_for_frames_does_not_accept_stale_geometry_or_add_fixed_sleep(self):
        expected={w['id']:w['frame'] for w in self.windows}
        with patch.object(wm,'query',return_value=self.windows),patch.object(wm.time,'sleep') as sleep:
            wm.wait_for_frames(1,expected)
        sleep.assert_not_called()
        stale=[dict(w,frame=dict(w['frame'],x=w['frame']['x']+10)) for w in self.windows]
        with patch.object(wm,'query',side_effect=[stale,self.windows]),patch.object(wm.time,'sleep') as sleep:
            wm.wait_for_frames(1,expected)
        sleep.assert_called_once_with(.005)


    def test_minimum_height_finishes_after_stabilizing(self):
        expected = {1:dict(x=872,y=586,w=846,h=523)}
        clamped = [w(1,872,586,846,620)]
        with patch.object(wm,'query',return_value=clamped), \
                patch.object(wm.time,'monotonic',side_effect=[0,0,.05,.101]), \
                patch.object(wm.time,'sleep'):
            self.assertEqual(wm.wait_for_frames(1,expected),clamped)

    def test_clamped_frames_must_stop_changing(self):
        expected = {1:dict(x=872,y=586,w=846,h=523)}
        resizing = [w(1,872,586,846,800)]
        clamped = [w(1,872,586,846,620)]
        with patch.object(wm,'query',side_effect=[resizing,clamped,clamped,clamped]) as query, \
                patch.object(wm.time,'monotonic',side_effect=[0,0,.09,.11,.20]), \
                patch.object(wm.time,'sleep'):
            self.assertEqual(wm.wait_for_frames(1,expected),clamped)
        self.assertEqual(query.call_count,4)

    def test_replacement_can_shrink_below_previous_occupants_minimum(self):
        expected = {1:dict(x=872,y=586,w=846,h=620)}
        actual = [w(1,872,586,846,523)]
        with patch.object(wm,'query',return_value=actual), \
                patch.object(wm.time,'monotonic',side_effect=[0,0,.101]), \
                patch.object(wm.time,'sleep'):
            self.assertEqual(wm.wait_for_frames(1,expected),actual)

    def test_wrong_positions_still_timeout(self):
        expected = {1:dict(x=872,y=586,w=846,h=523)}
        for frame in [w(1,800,586,846,620),w(1,872,500,700,620)]:
            with self.subTest(frame=frame), patch.object(wm,'query',return_value=[frame]), \
                    patch.object(wm.time,'monotonic',side_effect=[0,0,.2,1.01]), \
                    patch.object(wm.time,'sleep'):
                with self.assertRaisesRegex(RuntimeError,'Requested window frames'):
                    wm.wait_for_frames(1,expected)

    def test_closing_window_during_exact_frame_wait_stops(self):
        with patch.object(wm,'query',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'Windows changed'):
                wm.wait_for_frames(1,{1:dict(x=0,y=0,w=500,h=500)})

    def test_stable_minimum_height_overlap_can_be_reordered(self):
        clamped = [w(1,0,0,500,620),w(2,0,538,500,523)]
        with patch.object(wm,'query',return_value=clamped) as query, patch.object(wm.time,'sleep'):
            self.assertEqual(wm.settled_windows(1,{1,2}),clamped)
        self.assertEqual(query.call_count,4)

    def test_coincident_transient_tiles_are_not_accepted_as_minimum_sizes(self):
        coincident = [w(1,0,0,500,620),w(2,0,0,500,523)]
        with patch.object(wm,'query',return_value=coincident), patch.object(wm.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'have not settled'):
                wm.settled_windows(1,{1,2})



    def test_diagonally_separated_tile_is_not_neighbor(self):
        self.assertIsNone(wm.neighbor(w(1,0,0,100,100),[w(2,120,120,100,100)],'right'))

    def test_frame_updates_must_settle_before_next_action(self):
        overlapping = [w(1,0,0,500,500),w(2,0,0,500,500)]
        settled = [w(1,0,0,500,500),w(2,510,0,500,500)]
        with patch.object(wm,'query',side_effect=[overlapping,overlapping,settled,settled]) as query, patch.object(wm.time,'sleep'):
            self.assertEqual(wm.settled_windows(1,{1,2}),settled)
        self.assertEqual(query.call_count,4)

    def test_window_closing_during_rearrangement_stops_further_work(self):
        with patch.object(wm,'query',return_value=self.windows[:1]), patch.object(wm.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'Windows changed'):
                wm.settled_windows(1,{1,2,3})

    def test_aerospace_swap_and_edge_promotion(self):
        row = {'window-id':3,'workspace':'1','window-layout':'v_tiles','window-is-fullscreen':False,'monitor-id':1}
        for swap_success in [True,False]:
            calls = []
            def run(*args,**kwargs):
                calls.append(args)
                if args[1] == 'list-windows':
                    rows = [dict(row, **{'window-id':w['id']}) for w in self.windows] if '--workspace' in args else [row]
                    return SimpleNamespace(stdout=json.dumps(rows))
                if args[1] == 'swap': return SimpleNamespace(returncode=0 if swap_success else 1,stderr='')
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(wm,'run',side_effect=run), patch.object(wm,'desktop_geometry',return_value={'windows':self.windows}): wm.aerospace('right')
            self.assertIn(('aerospace','swap','--window-id',3,'right'),calls)
            if swap_success:
                self.assertEqual(len(calls),2)
            else:
                self.assertIn(('aerospace','layout','--workspace','1','--root','v_tiles'),calls)
                self.assertIn('--boundaries',calls[-1])
                self.assertIn('workspace',calls[-1])
                self.assertNotIn('--swap-focus',str(calls))

    def test_aerospace_full_side_crosses_or_stops_without_rebuilding(self):
        row = {'window-id':1,'workspace':'1','window-layout':'h_tiles','window-is-fullscreen':False,'monitor-id':2}
        # Monitor IDs deliberately differ from physical order and CG screen IDs.
        monitors = [{'monitor-id':2,'monitor-appkit-nsscreen-screens-id':10},
                    {'monitor-id':1,'monitor-appkit-nsscreen-screens-id':20}]
        geometry = {'windows':self.windows,'displays':[
            w(10,0,0,1010,1000),w(20,-1010,0,1010,1000)]}
        for direction, crosses in [('left',True),('up',False)]:
            # Sole window spans all sides and should also cross immediately.
            calls = []
            def run(*args,**kwargs):
                calls.append(args)
                if args[1] == 'list-windows': return SimpleNamespace(stdout=json.dumps([row]))
                if args[1] == 'swap': return SimpleNamespace(returncode=1,stderr='')
                if args[1] == 'list-monitors': return SimpleNamespace(stdout=json.dumps(monitors))
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(wm,'run',side_effect=run), patch.object(wm,'desktop_geometry',return_value=geometry):
                wm.aerospace(direction)
            moves = [c for c in calls if c[1] == 'move-node-to-monitor']
            self.assertEqual(moves, [('aerospace','move-node-to-monitor','--window-id',1,'--focus-follows-window','left')] if crosses else [])
            self.assertFalse(any(c[1] == 'flatten-workspace-tree' for c in calls))

    def test_aerospace_command_failure_does_not_rebuild_layout(self):
        row = {'window-id':3,'workspace':'1','window-layout':'h_tiles','window-is-fullscreen':False}
        with patch.object(wm,'run',side_effect=[SimpleNamespace(stdout=json.dumps([row])),SimpleNamespace(returncode=1,stderr='Server disconnected')]) as command:
            with self.assertRaisesRegex(RuntimeError,'disconnected'): wm.aerospace('right')
        self.assertEqual(command.call_count,2)


if __name__ == '__main__': unittest.main()
