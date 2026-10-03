import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('resize', ROOT/'wm-resize.py')
resize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resize)
spec = importlib.util.spec_from_file_location('direction', ROOT/'wm-direction.py')
direction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(direction)


def w(id, x, y, width, height, **extra):
    return dict(id=id, space=1, display=1, frame=dict(x=x, y=y, w=width, h=height), **extra)


class ResizeTests(unittest.TestCase):
    def test_right_column_never_probes_false_outer_fence(self):
        for delta in (16, 32, 64, -16, -32, -64):
            for width in (846, 878, 909, 814):
                wm = Mock()
                wm.query.return_value = w(1, 1718-width, 48, width, 1061,
                                          **{'split-type': 'vertical', 'split-child': 'second_child'})
                resize.resize(wm, 'width', delta)
                wm.window.assert_called_once_with(1, '--resize', f'left:{-delta}:0')
                self.assertEqual(wm.query.call_count, 1)

    def test_both_axes_and_children_use_consistent_signs(self):
        for axis, split, first, second in [('width', 'vertical', 'right:32:0', 'left:-32:0'),
                                           ('height', 'horizontal', 'bottom:0:32', 'top:0:-32')]:
            for child, expected in [('first_child', first), ('second_child', second)]:
                wm = Mock()
                wm.query.return_value = w(1, 0, 0, 500, 500,
                                          **{'split-type': split, 'split-child': child})
                resize.resize(wm, axis, 32)
                wm.window.assert_called_once_with(1, '--resize', expected)

    def test_stacked_row_resizes_ancestor_column(self):
        left = w(1, 10, 48, 846, 1061)
        top = w(2, 872, 48, 846, 620)
        bottom = w(3, 872, 586, 846, 523, **{'split-type': 'horizontal'})
        wm = Mock(neighbor=direction.neighbor, eligible=direction.eligible)
        wm.query.side_effect = [bottom, [left, top, bottom]]
        resize.resize(wm, 'width', 32)
        wm.window.assert_called_once_with(3, '--resize', 'left:-32:0')

    def test_single_tiled_window_does_not_resize(self):
        selected = w(1, 0, 0, 1000, 1000, **{'split-type': 'none'})
        wm = Mock(neighbor=direction.neighbor, eligible=direction.eligible)
        wm.query.side_effect = [selected, [selected]]
        resize.resize(wm, 'width', 32)
        wm.window.assert_not_called()

    def test_floating_window_resizes_from_bottom_right(self):
        wm = Mock()
        wm.query.return_value = w(1, 0, 0, 500, 500, **{'is-floating': True})
        resize.resize(wm, 'height', -32)
        wm.window.assert_called_once_with(1, '--resize', 'bottom:0:-32')

    def test_fullscreen_window_is_untouched(self):
        wm = Mock()
        wm.query.return_value = w(1, 0, 0, 1000, 1000, **{'has-fullscreen-zoom': True})
        resize.resize(wm, 'width', 32)
        wm.window.assert_not_called()


if __name__ == '__main__':
    unittest.main()
