"""Activation checks use fake commands and never restart the live daemon."""
import importlib.util
import json
import tempfile
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
        self.assertEqual(calls[-1], [str(activation.PROFILE), "--force"])
        self.assertEqual(calls.count([str(activation.PROFILE), "--force"]), 1)

    def test_unavailable_daemon_does_not_apply_profile(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, '[\n', '')
        with patch.object(activation.subprocess, 'run', side_effect=run) as commands, \
                patch.object(activation.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'did not respond'):
                activation.restart(Path('/fake/yabai'))
        self.assertNotIn([str(activation.PROFILE), "--force"], [c.args[0] for c in commands.call_args_list])


    def test_activation_failure_restores_previous_binary_and_profile(self):
        for failure in (RuntimeError("unavailable"), OSError("missing executable"),
                        subprocess.CalledProcessError(1, "profile")):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                (root / 'bin').mkdir()
                old, new = root / 'old-yabai', root / 'new-yabai'
                old.touch()
                new.touch()
                link = root / 'bin/yabai'
                link.symlink_to(old)
                profiles = []
                def run(args, **kwargs):
                    failure_command = ([str(activation.PROFILE), '--force']
                                       if isinstance(failure, subprocess.CalledProcessError)
                                       else ['launchctl', 'kickstart', '-k', activation.SERVICE])
                    if args == failure_command and link.resolve() == new:
                        raise failure
                    if args == [str(activation.PROFILE), '--force']:
                        profiles.append(link.resolve())
                    data = '[{"index":1}]' if '--spaces' in args else '[{"label":"dotfiles-display_resized"}]'
                    return subprocess.CompletedProcess(args, 0, data, '')
                with patch.object(activation, 'BINARY', new), \
                        patch.object(activation, 'STATE', root / 'backup.json'), \
                        patch.object(activation.subprocess, 'check_output', return_value=str(root)), \
                        patch.object(activation.subprocess, 'run', side_effect=run):
                    with self.assertRaises(type(failure)):
                        activation.main('activate')
                self.assertEqual(link.resolve(), old)
                self.assertEqual(profiles, [old])
                self.assertEqual(json.loads((root / 'backup.json').read_text())['target'], str(old))

    def test_explicit_rollback_restores_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / 'bin').mkdir()
            old, new = root / 'old-yabai', root / 'new-yabai'
            old.touch()
            new.touch()
            link = root / 'bin/yabai'
            link.symlink_to(new)
            backup = root / 'backup.json'
            backup.write_text(json.dumps({'link': str(link), 'target': str(old)}))
            profiles = []
            def run(args, **kwargs):
                if args == [str(activation.PROFILE), '--force']:
                    profiles.append(link.resolve())
                data = '[{"index":1}]' if '--spaces' in args else '[{"label":"dotfiles-display_resized"}]'
                return subprocess.CompletedProcess(args, 0, data, '')
            with patch.object(activation, 'BINARY', new), \
                    patch.object(activation, 'STATE', backup), \
                    patch.object(activation.subprocess, 'check_output', return_value=str(root)), \
                    patch.object(activation.subprocess, 'run', side_effect=run), \
                    patch('builtins.print'):
                activation.main('rollback')
            self.assertEqual(link.resolve(), old)
            self.assertEqual(profiles, [old])


if __name__ == '__main__':
    unittest.main()
