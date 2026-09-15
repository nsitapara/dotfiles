import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wm_size', ROOT / 'wm-size.py')
size = importlib.util.module_from_spec(spec)
spec.loader.exec_module(size)


def window(id, x, width, y=0, height=1000):
    return dict(id=id, frame=dict(x=x, y=y, w=width, h=height), space=1, display=1)


class Presets(unittest.TestCase):
    def test_steps_and_endpoints(self):
        for width, step, expected in [(1000, 1, 300), (1300, 1, 200),
                                      (1500, 1, None), (1500, -1, -200),
                                      (1300, -1, -300), (1000, -1, None),
                                      (1200, 1, 100), (1200, -1, -200),
                                      (999, 1, 301), (1301, -1, -301)]:
            with self.subTest(width=width, step=step):
                a, b = window(1, 0, width), window(2, width+16, 2000-width)
                result = size.resize_plan(a, [a, b], step)
                self.assertEqual(result, None if expected is None else ('right', expected))

    def test_right_column_with_stacked_windows(self):
        left = window(1, -2016, 1000)
        top = window(2, -1000, 1000, 0, 492)
        bottom = window(3, -1000, 1000, 508, 492)
        self.assertEqual(size.resize_plan(bottom, [left, top, bottom], 1), ('left', 300))

    def test_declines_ambiguous_layouts(self):
        cases = [
            [window(1, 0, 1000)],
            [window(1, 0, 600), window(2, 616, 600), window(3, 1232, 600)],
            [window(1, 0, 1100), window(2, 1016, 1000)],
            [window(1, 0, 1000), window(2, 1016, 1000, 0, 700), window(3, 1016, 1000, 500, 500)],
            [window(1, 0, 1000), window(2, 1016, 1000, 0, 492), window(3, 1016, 900, 508, 492)],
        ]
        for windows in cases:
            self.assertIsNone(size.resize_plan(windows[0], windows, 1))

    def test_yabai_moves_only_the_inner_edge(self):
        for selected_id, expected in [(1, 'right:300:0'), (2, 'left:-300:0')]:
            windows = [window(1, 0, 1000), window(2, 1016, 1000)]
            wm = Mock()
            wm.eligible.return_value = True
            wm.query.side_effect = [windows[selected_id-1], {'type': 'bsp'}, windows,
                                   {'frame': {'x': 0, 'w': 2026}}]
            wm.run.side_effect = [Mock(stdout='16'), Mock(stdout='10')]
            size.resize_yabai(wm, 1)
            wm.window.assert_called_once_with(selected_id, '--resize', expected)
            self.assertTrue(all(call.args[2] == 'config' for call in wm.run.call_args_list))

    def test_laptop_minimum_sizes_do_not_disable_presets(self):
        left = window(1, 10, 1269, 48, 1061)
        top = window(2, 1294, 840, 48, 697)
        bottom = window(3, 1294, 500, 760, 375)
        # Actual right-hand apps exceed their 423px tiles. The split still
        # occupies 75/25, and shrinking the left column must restore 65/35.
        self.assertEqual(size.resize_plan(left, [left, top, bottom], -1,
                         gap=15, right_edge=1717), ('right', -169))
        self.assertEqual(size.resize_plan(bottom, [left, top, bottom], 1,
                         gap=15, right_edge=1717), ('left', 423))

    def test_minimum_height_does_not_change_column_membership(self):
        left = window(1, 10, 846, 48, 1061)
        top = window(2, 872, 846, 48, 697)
        bottom = window(3, 872, 846, 760, 375)
        self.assertEqual(size.resize_plan(bottom, [left, top, bottom], 1), ('left', 254))

    def test_yabai_declines_zoom_and_stack(self):
        for flag in ['has-fullscreen-zoom', 'has-parent-zoom', 'stack-index']:
            windows = [window(1, 0, 1000), window(2, 1016, 1000)]
            windows[1][flag] = 1
            wm = Mock()
            wm.eligible.return_value = True
            wm.query.side_effect = [windows[0], {'type': 'bsp'}, windows]
            size.resize_yabai(wm, 1)
            wm.window.assert_not_called()

    def test_aerospace_resizes_selected_column_without_focus_or_layout_changes(self):
        rows = [dict(**{'window-id': n, 'window-layout': 'v_tiles' if n > 1 else 'h_tiles',
                       'window-is-fullscreen': False, 'workspace': '1'}) for n in range(1, 4)]
        wm = Mock(AS_FORMAT='format')
        wm.run.side_effect = [Mock(stdout=json.dumps([rows[2]])), Mock(stdout=json.dumps(rows)), Mock()]
        wm.aerospace_tiled.return_value = True
        wm.desktop_geometry.return_value = dict(windows=[window(1, 0, 1000),
            window(2, 1016, 1000, 0, 492), window(3, 1016, 1000, 508, 492)])
        size.resize_aerospace(wm, 1)
        self.assertEqual(wm.run.call_count, 3)
        wm.run.assert_called_with('aerospace', 'resize', '--window-id', 3, 'width', '+300')


if __name__ == '__main__':
    unittest.main()
