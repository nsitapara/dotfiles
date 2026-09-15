import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'focus_previous', ROOT / 'yabai/.config/yabai/scripts/focus-previous.py')
focus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(focus)


class PreviousWindowTests(unittest.TestCase):
    def setUp(self):
        self.a = {'id': 1, 'pid': 10, 'is-floating': True}
        self.b = {'id': 2, 'pid': 20}
        self.state = {}
        focus.remember(self.state, self.a)
        focus.remember(self.state, self.b)

    def test_duplicate_focus_does_not_lose_previous(self):
        focus.remember(self.state, self.b)
        focus.remember(self.state, None)
        self.assertEqual(self.state['previous'], focus.identity(self.a))

    def test_floating_window_and_return(self):
        with patch.object(focus, 'query', side_effect=[self.b, self.a, self.a, self.b]), \
                patch.object(focus.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            focus.focus_previous(self.state)
            self.assertEqual(self.state['current'], focus.identity(self.a))
            focus.focus_previous(self.state)
            self.assertEqual(self.state['current'], focus.identity(self.b))
            self.assertEqual([c.args[0][-1] for c in run.call_args_list], ['1', '2'])

    def test_closed_reused_hidden_or_minimized_target_is_skipped(self):
        for target in [None, {**self.a, 'pid': 99},
                       {**self.a, 'is-hidden': True}, {**self.a, 'is-minimized': True}]:
            with self.subTest(target=target):
                state = dict(self.state)
                with patch.object(focus, 'query', side_effect=[self.b, target]), \
                        patch.object(focus.subprocess, 'run') as run:
                    focus.focus_previous(state)
                    run.assert_not_called()
                    self.assertIsNone(state['previous'])

    def test_focus_failure_keeps_history(self):
        before = dict(self.state)
        with patch.object(focus, 'query', side_effect=[self.b, self.a]), \
                patch.object(focus.subprocess, 'run', return_value=Mock(returncode=1, stderr='failed')):
            with self.assertRaises(RuntimeError):
                focus.focus_previous(self.state)
        self.assertEqual(self.state, before)


if __name__ == '__main__':
    unittest.main()
