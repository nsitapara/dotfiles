"""Directional swaps must preserve sizes; edge promotion stays in the workspace."""
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
        with patch.object(wm,'query',side_effect=[self.windows[0],{'type':'bsp'},self.windows]), patch.object(wm,'window') as command:
            wm.yabai('left')
        command.assert_not_called()

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
        row = {'window-id':3,'workspace':'1','window-layout':'v_tiles','window-is-fullscreen':False}
        for swap_success in [True,False]:
            calls = []
            def run(*args,**kwargs):
                calls.append(args)
                if args[1] == 'list-windows': return SimpleNamespace(stdout=json.dumps([row]))
                if args[1] == 'swap': return SimpleNamespace(returncode=0 if swap_success else 1,stderr='')
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(wm,'run',side_effect=run): wm.aerospace('right')
            self.assertIn(('aerospace','swap','--window-id',3,'right'),calls)
            if swap_success:
                self.assertEqual(len(calls),2)
            else:
                self.assertIn(('aerospace','layout','--workspace','1','--root','v_tiles'),calls)
                self.assertIn('--boundaries',calls[-1])
                self.assertIn('workspace',calls[-1])
                self.assertNotIn('--swap-focus',str(calls))

    def test_aerospace_command_failure_does_not_rebuild_layout(self):
        row = {'window-id':3,'workspace':'1','window-layout':'h_tiles','window-is-fullscreen':False}
        with patch.object(wm,'run',side_effect=[SimpleNamespace(stdout=json.dumps([row])),SimpleNamespace(returncode=1,stderr='Server disconnected')]) as command:
            with self.assertRaisesRegex(RuntimeError,'disconnected'): wm.aerospace('right')
        self.assertEqual(command.call_count,2)


if __name__ == '__main__': unittest.main()
