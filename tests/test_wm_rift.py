"""Rift policy tests. No desktop commands or processes run here."""
import contextlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wm_rift as rift
from scripts.wm import rift_geometry as geometry


def frame(x=0, y=0, w=1000, h=800):
    return dict(origin=dict(x=x, y=y), size=dict(width=w, height=h))


class RiftTests(unittest.TestCase):
    def test_workspace_mapping_uses_global_number_across_displays(self):
        plan = [dict(uuid='left', workspaces=[1,3,5]), dict(uuid='right', workspaces=[2,4,6])]
        mapping = rift.mappings(plan)
        self.assertEqual(mapping[5]['uuid'], 'left')
        self.assertEqual(mapping[4]['uuid'], 'right')
        self.assertNotIn(7, mapping)

    def test_bar_keeps_window_identity_duplicate_chrome_and_physical_display_ids(self):
        display = dict(uuid='left', screen_id=71, space=9, is_active_context=True, frame=frame())
        windows = [dict(window_server_id=i, app_name=app) for i,app in
                   [(10,'Google Chrome'), (20,'Google Chrome'), (30,'Terminal')]]
        workspace = dict(index=0, is_active=True, windows=windows)
        plan = [dict(uuid='left', index=0, id=71, workspaces=[1,3,5])]
        def query(kind, *_):
            return [display] if kind == 'displays' else [workspace]
        with patch.object(rift,'read_state',return_value=plan), patch.object(rift,'query',side_effect=query), \
             patch.object(rift,'run',return_value=types.SimpleNamespace(stdout='[{"DirectDisplayID":71,"arrangement-id":2}]')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output): rift.bar()
        data = json.loads(output.getvalue())
        self.assertEqual([w['app'] for w in data['windows']], ['Google Chrome','Google Chrome','Terminal'])
        self.assertEqual(data['displays'][0]['id'],71)
        self.assertEqual(data['bar_displays'][0]['arrangement-id'],2)
        self.assertEqual(data['spaces'][0]['label'],'ws1')
        self.assertEqual(data['targets'][0]['uuid'],'left')

    def test_snapshot_includes_only_active_native_spaces_and_marks_visibility(self):
        display = dict(uuid='left', active_space_ids=[9], inactive_space_ids=[10], space=9)
        w = dict(window_server_id=1, id=dict(pid=2,idx=3), is_floating=False, is_focused=False,frame=frame())
        def query(kind, space=None):
            if kind == 'displays': return [display]
            self.assertEqual(space,9)
            return [dict(index=0,is_active=False,windows=[w])]
        with patch.object(rift,'query',side_effect=query): result=rift.snapshot()
        self.assertFalse(result['windows'][0]['visible'])
        self.assertEqual(result['windows'][0]['workspace'],1)

    def test_pixel_resize_uses_nearest_matching_parent_and_accepts_negative_cli_value(self):
        identity=dict(pid=2,idx=3)
        leaf=dict(window_id=identity,children=[],layout_kind=None)
        column=dict(window_id=None,children=[leaf],layout_kind='horizontal',frame=frame(w=515))
        tree=dict(window_id=None,children=[column],layout_kind='horizontal',frame=frame(w=2000))
        api=Mock()
        api.current_slot.return_value=(dict(frame=frame()),dict(layout_mode='bsp'))
        api.query.return_value=dict(container_tree=tree)
        api.rect.side_effect=rift.rect
        selected=dict(floating=False,rift_id=identity)
        geometry.resize_width(api,selected,-32)
        api.execute.assert_called_once_with('window','resize-by','--amount=-0.128')

    def test_expansion_never_uses_bsp_cross_display_command(self):
        selected=dict(id=1,rift_id=dict(pid=1,idx=1),display='left',visible=True,focused=True,
                      floating=False,frame=dict(x=0,y=0,w=500,h=400))
        other=dict(selected,id=2,focused=False,frame=dict(x=0,y=415,w=500,h=385))
        display=dict(uuid='left',screen_id=1,frame=frame())
        api=Mock()
        api.snapshot.return_value=dict(windows=[selected,other],displays=[display])
        api.current_slot.return_value=(display,dict(layout_mode='bsp'))
        api.rect.side_effect=rift.rect
        with patch.object(geometry,'place_side') as place:
            geometry.directional(api,'left',move=True)
        place.assert_called_once_with(api,selected,[selected,other],'left')
        api.execute.assert_not_called()
        api.move_window.assert_not_called()

    def test_swap_neighbor_preserves_workspace(self):
        left=dict(id=1,rift_id=dict(pid=1,idx=1),display='left',visible=True,focused=True,
                  floating=False,frame=dict(x=0,y=0,w=500,h=800))
        right=dict(left,id=2,rift_id=dict(pid=1,idx=2),focused=False,frame=dict(x=515,y=0,w=485,h=800))
        display=dict(uuid='left',screen_id=1,frame=frame())
        api=Mock(); api.snapshot.return_value=dict(windows=[left,right],displays=[display])
        api.current_slot.return_value=(display,dict(layout_mode='bsp')); api.rect.side_effect=rift.rect
        geometry.directional(api,'right',move=True)
        self.assertEqual(api.execute.call_args.args[:2],('layout','swap-windows'))
        api.move_window.assert_not_called()


if __name__ == '__main__': unittest.main()
