"""Detached tabs must settle after release without resetting valid splits."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'settle_tiles', ROOT / 'yabai/.config/yabai/scripts/settle-tiles.py')
chrome = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chrome)


def window(id, y, height, **extra):
    return dict({'id': id, 'pid': 42, 'space': 1, 'app': 'Google Chrome',
                 'is-visible': True, 'subrole': 'AXStandardWindow',
                 'split-type': 'horizontal',
                 'frame': {'x': 1288, 'y': y, 'w': 1262, 'h': height}}, **extra)


class SettleChromeTests(unittest.TestCase):
    def setUp(self):
        # Frames observed on the user's Space 1, overlapping by 223 pixels.
        self.windows = [window(10, 50, 375), window(20, 202, 1230)]
        self.space = {'type': 'bsp', 'is-visible': True}
        self.now = 0
        self.calls = []
        self.queries = []

    def query(self, *args):
        self.queries.append((self.now, args))
        if args[:2] == ('--windows', '--window'):
            return next((w for w in self.windows if w['id'] == args[2]), None)
        if args[0] == '--spaces':
            return self.space
        return self.windows

    def command(self, *args, **kwargs):
        self.calls.append((self.now, args))
        self.windows[0]['frame'].update(y=50, h=683)
        self.windows[1]['frame'].update(y=749, h=683)

    def sleep(self, seconds):
        self.now += seconds

    def run_settle(self, down=lambda: False):
        with patch.object(chrome, 'query', self.query), patch.object(chrome, 'run', self.command), \
             patch.object(chrome.time, 'monotonic', lambda: self.now), \
             patch.object(chrome.time, 'sleep', self.sleep):
            chrome.settle(20, down)

    def test_live_overlap_repaired_only_after_long_drag_finishes(self):
        self.run_settle(lambda: self.now < 3)
        self.assertEqual(len(self.calls), 1)
        self.assertGreaterEqual(self.calls[0][0], 3.35)
        self.assertEqual(self.calls[0][1],
                         ('yabai', '-m', 'space', 1, '--padding', 'rel:0:0:0:0'))
        self.assertFalse(chrome.overlaps(*self.windows))
        self.assertFalse(any(0 < t < 3 for t, _ in self.queries))

    def test_valid_unequal_splits_stay_unchanged(self):
        self.windows[1]['frame'].update(y=441, h=991)
        before = copy.deepcopy(self.windows)
        self.run_settle()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.windows, before)

    def test_float_stack_minimized_hidden_fullscreen_and_zoom_are_not_repaired(self):
        for flag in ('is-floating', 'stack-index', 'is-minimized', 'is-hidden',
                     'is-native-fullscreen', 'has-parent-zoom', 'has-fullscreen-zoom'):
            with self.subTest(flag=flag):
                self.setUp()
                self.windows[1][flag] = True
                self.run_settle()
                self.assertEqual(self.calls, [])

    def test_hidden_and_non_bsp_spaces_are_not_repaired(self):
        for space in ({'type': 'bsp', 'is-visible': False},
                      {'type': 'stack', 'is-visible': True}):
            self.setUp()
            self.space = space
            self.run_settle()
            self.assertEqual(self.calls, [])

    def test_closed_moved_or_reused_window_is_not_repaired(self):
        for change in ('close', 'space', 'pid'):
            self.setUp()

            def down():
                if self.now >= .2:
                    if change == 'close':
                        self.windows[:] = self.windows[:1]
                    else:
                        self.windows[1][change] = 99
                return self.now < .2

            self.run_settle(down)
            self.assertEqual(self.calls, [])

    def test_late_chrome_resize_is_repaired_on_second_check(self):
        def down():
            if .5 <= self.now <= .6:
                self.windows[1]['frame'].update(y=202, h=1230)
            return False

        self.run_settle(down)
        self.assertEqual(len(self.calls), 2)

    def test_mouse_held_forever_exits_without_resizing(self):
        self.run_settle(lambda: True)
        self.assertEqual(self.calls, [])
        self.assertLess(self.now, 30.2)

    def test_new_drag_during_query_prevents_mutation(self):
        with patch.object(chrome, 'query', self.query), patch.object(chrome, 'run') as run:
            chrome.repair(20, (42, 1), lambda: True)
            run.assert_not_called()


def tile(id, x, y, w, h):
    return {'id': id, 'is-visible': True, 'subrole': 'AXStandardWindow', 'split-type': 'none',
            'frame': {'x': x, 'y': y, 'w': w, 'h': h}}


class SettleSpaceTests(unittest.TestCase):
    """Observed ws1/ws5 frames on the 2560x1440 display with 50/8/10/10 padding."""
    LEFT, RIGHT = (10, 50, 1262, 1382), (1288, 50, 1262, 1382)

    def run_space(self, frames, after_reflush=None, after_rebuild=None, down=False):
        windows = [tile(i, *f) for i, f in enumerate(frames)]
        calls = []
        config = {'top_padding': '50', 'bottom_padding': '8', 'left_padding': '10',
                  'right_padding': '10', 'window_gap': '15'}

        def query(*args):
            if args[0] == '--spaces':
                return {'type': 'bsp', 'is-visible': True, 'display': 1}
            if args[0] == '--displays':
                return {'frame': {'x': 0, 'y': 0, 'w': 2560, 'h': 1440}}
            return windows

        def run(*args, **kwargs):
            if args[2] == 'config':
                return type('Result', (), {'stdout': config[args[-1]]})
            calls.append(args[4:])
            for frame in (after_reflush if args[4] == '--padding' else after_rebuild) or []:
                windows[frame[0]]['frame'].update(zip('xywh', frame[1:]))

        with patch.object(chrome, 'query', query), patch.object(chrome, 'run', run), \
             patch.object(chrome.time, 'sleep', lambda s: None):
            chrome.settle_space(1, lambda: down)
        return calls

    def test_layouts(self):
        cases = {
            'full single tile': ([(10, 50, 2540, 1382)], None, None, []),
            'unequal columns': ([(10, 50, 740, 1382), (765, 50, 1785, 1382)], None, None, []),
            # ws5: T3 kept its old half-height frame; a reflush fixes it, ratios kept.
            'stale frame': ([self.LEFT, (1288, 50, 1262, 683)], [(1,) + self.RIGHT], None,
                            [('--padding', 'rel:0:0:0:0')]),
            # ws1: an untracked window's leaf keeps its tile empty after a reflush.
            'ghost tile': ([(1288, 749, 1262, 683)], None, [(0, 10, 50, 2540, 1382)],
                           [('--padding', 'rel:0:0:0:0'), ('--layout', 'bsp')]),
        }
        for name, (frames, reflush, rebuild, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.run_space(frames, reflush, rebuild), expected)

    def test_drag_in_progress_is_left_alone(self):
        self.assertEqual(self.run_space([(1288, 749, 1262, 683)], down=True), [])


if __name__ == '__main__':
    unittest.main()
