import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'focus_previous', ROOT / 'yabai/.config/yabai/scripts/focus-previous.py')
focus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(focus)


class PreviousWindowTests(unittest.TestCase):
    def setUp(self):
        self.a = {'id': 1, 'pid': 10, 'is-floating': True, 'is-visible': True, 'space': 1}
        self.b = {'id': 2, 'pid': 20, 'is-visible': True, 'space': 2}
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

    def test_other_space_is_activated_before_window_focus(self):
        target = {**self.a, 'is-visible': False}
        with patch.object(focus, 'query', side_effect=[
                self.b, target, {'is-visible': False}, {'is-visible': True}]), \
                patch.object(focus.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            focus.focus_previous(self.state)
        self.assertEqual([c.args[0] for c in run.call_args_list], [
            ['yabai', '-m', 'space', '--focus', '1'],
            ['yabai', '-m', 'window', '--focus', '1'],
        ])
        self.assertEqual(self.state['current'], focus.identity(self.a))

    def test_failed_space_switch_does_not_trigger_animated_window_focus(self):
        before = dict(self.state)
        with patch.object(focus, 'query', side_effect=[
                self.b, {**self.a, 'is-visible': False}, {'is-visible': False}]), \
                patch.object(focus.subprocess, 'run', return_value=Mock(returncode=1, stderr='failed')) as run:
            with self.assertRaises(RuntimeError):
                focus.focus_previous(self.state)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.state, before)

    def test_focus_signal_does_not_wait_on_in_progress_toggle(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(focus.Path, 'home', return_value=Path(directory)), \
                patch.object(focus.fcntl, 'flock', side_effect=BlockingIOError) as lock, \
                patch.object(focus, 'query') as query:
            focus.main('record')
            self.assertTrue(lock.call_args.args[1] & focus.fcntl.LOCK_NB)
            query.assert_not_called()

    def test_invisible_space_timeout_does_not_focus_off_space_window(self):
        with patch.object(focus, 'query', side_effect=[
                self.b, {**self.a, 'is-visible': False}, {'is-visible': False}]), \
                patch.object(focus.time, 'monotonic', side_effect=[0, 2]), \
                patch.object(focus.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            with self.assertRaisesRegex(RuntimeError, 'did not become visible'):
                focus.focus_previous(self.state)
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
