"""Directional movement swaps, fills a side, then crosses without wrapping."""
import importlib.util
import json
from pathlib import Path
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
        with patch.object(wm,'query',side_effect=query), patch.object(wm,'window') as command, patch.object(wm,'settled_windows'):
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
            with self.subTest(count=len(windows)), patch.object(wm,'query',side_effect=[
                    windows[0],{'type':'bsp'},windows,displays,[{'index':4,'is-visible':True,'type':'bsp'}],[]]), patch.object(wm,'window') as command, patch.object(wm,'run') as run:
                wm.yabai('left')
            command.assert_called_once_with(1,'--display',2)
            self.assertEqual([c.args for c in run.call_args_list], [
                ('yabai','-m','display','--focus',2),('yabai','-m','window','--focus',1)])

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
        with patch.object(wm,'query',side_effect=[displays,[{'index':4,'is-visible':True,'type':'bsp'}],self.windows]), patch.object(wm,'window') as command, patch.object(wm,'run'):
            wm.cross_yabai(selected,'left')
        self.assertEqual([c.args for c in command.call_args_list],[
            (3,'--insert','west'),(3,'--insert','east'),(8,'--display',2)])

    def test_yabai_focus_enters_near_edge_without_moving_windows(self):
        displays = [dict(id=10,index=1,frame=dict(x=1010,y=0,w=1010,h=1000),**{'has-focus':True}),
                    dict(id=20,index=2,frame=dict(x=0,y=0,w=1010,h=1000))]
        windows = [dict(w,display=2,**{'is-visible':True}) for w in self.windows]
        windows.append(w(8,1010,505,500,495,**{'has-focus':True,'is-visible':True}))
        with patch.object(wm,'query',side_effect=[displays,windows]),patch.object(wm,'run') as command:
            wm.focus_yabai('left')
        self.assertEqual([c.args for c in command.call_args_list],[
            ('yabai','-m','display','--focus',2),('yabai','-m','window','--focus',3)])

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

    def test_aerospace_perpendicular_layout_arrives_on_incoming_side(self):
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
        with patch.object(wm,'query',side_effect=[self.windows[2],{'type':'bsp'},self.windows,promoted,promoted]), patch.object(wm,'window') as command, patch.object(wm,'settled_windows',return_value=fresh):
            wm.yabai('right')
        calls = [c.args for c in command.call_args_list]
        self.assertIn((2,'--warp',1),calls)
        self.assertIn((3,'--ratio','abs:0.5'),calls)
        self.assertFalse(any('--toggle' in c or '--space' in c for c in calls))

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
