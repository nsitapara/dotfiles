"""Activation checks use fake commands and never restart the live daemon."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('activation', ROOT / 'scripts/use-yabai-macos27.py')
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


class ActivationTests(unittest.TestCase):
    def test_restart_waits_for_valid_queries_and_config_then_restores_profile(self):
        responses = iter(['[\n', '[]', '[{"index":1}]', '[{"index":1}]'])
        signal_responses = iter(['[]', '[{"label":"dotfiles-display_resized"}]'])
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            data = ''
            if args[1:3] == ['-m', 'query']:
                data = next(responses)
            elif args[1:3] == ['-m', 'signal']:
                data = next(signal_responses)
            return subprocess.CompletedProcess(args, 0, data, '')
        with patch.object(activation.subprocess, 'run', side_effect=run), \
                patch.object(activation.time, 'sleep') as sleep:
            activation.restart(Path('/fake/yabai'))
        self.assertEqual(sleep.call_count, 3)
        self.assertEqual(calls[-1], [str(activation.PROFILE)])
        self.assertEqual(calls.count([str(activation.PROFILE)]), 1)

    def test_unavailable_daemon_does_not_apply_profile(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, '[\n', '')
        with patch.object(activation.subprocess, 'run', side_effect=run) as commands, \
                patch.object(activation.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'did not respond'):
                activation.restart(Path('/fake/yabai'))
        self.assertNotIn([str(activation.PROFILE)], [c.args[0] for c in commands.call_args_list])


if __name__ == '__main__':
    unittest.main()
