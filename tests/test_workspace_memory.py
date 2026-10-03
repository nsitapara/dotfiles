import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'workspace_memory', ROOT / 'yabai/.config/yabai/scripts/workspace-memory.py')
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)

LAPTOP, LG = {'id': 1, 'index': 1}, {'id': 3, 'index': 2}
SINGLE = [dict(LAPTOP, workspaces=[1, 3, 5]), dict(LG, workspaces=[2, 4, 6])]


def spaces(*labels_by_display):
    """spaces(['ws1', 'ws3'], ['ws2']) -> desktops numbered left to right."""
    out = []
    for display, labels in enumerate(labels_by_display, 1):
        for label in labels:
            out.append({'index': len(out) + 1, 'display': display, 'label': label})
    return out


class WorkspaceMemoryTests(unittest.TestCase):
    def test_saves_only_while_layout_is_intact(self):
        full = spaces(['ws1', 'ws3', 'ws5'], ['ws2', 'ws4', 'ws6'])
        cases = [
            ('applied layout', full, [LAPTOP, LG], SINGLE, True),
            ('monitor just unplugged', spaces(['ws1', 'ws3', 'ws5', 'ws2', 'ws4', 'ws6']), [LAPTOP], SINGLE, False),
            ('monitor just plugged in', full, [LAPTOP, LG], [dict(LAPTOP, workspaces=[1, 2, 3, 4, 5, 6])], False),
            ('desktops still missing', spaces(['ws1', 'ws3', 'ws5'], ['ws2']), [LAPTOP, LG], SINGLE, False),
            ('no layout yet', full, [LAPTOP, LG], None, False),
        ]
        for name, current, displays, layout, expected in cases:
            with self.subTest(name):
                self.assertEqual(memory.settled(current, displays, layout), expected)

    def test_windows_return_to_their_workspace_after_macos_merges_desktops(self):
        saved = {'10': 'ws1', '20': 'ws2', '40': 'ws4', '60': 'ws6'}
        # Undock: macOS merged the monitor's visible ws2 into ws1 and relabelling
        # by position handed ws4's desktop the ws2 label.
        now = spaces(['ws1', 'ws2', 'ws3', 'ws4', 'ws5', 'ws6'])
        windows = [{'id': 10, 'space': 1}, {'id': 20, 'space': 1},
                   {'id': 40, 'space': 2}, {'id': 60, 'space': 6}, {'id': 99, 'space': 3}]
        self.assertEqual(sorted(memory.moves(saved, now, windows)), [(20, 'ws2'), (40, 'ws4')])

    def test_missing_workspaces_and_closed_windows_are_left_alone(self):
        saved = {'40': 'ws4', '70': 'ws1'}
        now = spaces(['ws1', 'ws3', 'ws5'], ['ws2'])
        self.assertEqual(memory.moves(saved, now, [{'id': 40, 'space': 1}]), [])


if __name__ == '__main__':
    unittest.main()
