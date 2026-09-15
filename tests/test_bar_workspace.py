import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bar_workspace', ROOT/'wm-bar-workspace.py')
bar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bar)


class BarWorkspaceTests(unittest.TestCase):
    def test_yabai_restores_preference_even_if_switch_fails(self):
        for failing in (False, True):
            direction = Mock()
            direction.run.return_value = Mock(stdout='on\n')
            focus = Mock()
            if failing: focus.switch.side_effect = RuntimeError('unavailable')
            with patch.object(bar, 'module', side_effect=[direction, focus]):
                if failing:
                    with self.assertRaises(RuntimeError): bar.yabai_switch('2')
                else: bar.yabai_switch('2')
            self.assertEqual([call.args for call in direction.run.call_args_list], [
                ('yabai','-m','config','mouse_follows_focus'),
                ('yabai','-m','config','mouse_follows_focus','off'),
                ('yabai','-m','config','mouse_follows_focus','on')])

    def test_yabai_does_not_enable_previously_disabled_mouse_follow(self):
        direction, focus = Mock(), Mock()
        direction.run.return_value = Mock(stdout='off\n')
        with patch.object(bar, 'module', side_effect=[direction, focus]): bar.yabai_switch('2')
        self.assertEqual(direction.run.call_count, 1)
        focus.switch.assert_called_once_with('2')

    def test_aerospace_cleans_guard_on_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bar, 'STATE', Path(directory)), \
                patch.object(bar.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'aerospace')):
            with self.assertRaises(subprocess.CalledProcessError): bar.aerospace_switch('2')
            self.assertFalse((Path(directory)/'bar-mouse-suppressed').exists())

    def test_aerospace_guard_skips_only_live_click(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/'marker'
            executable = root/'aerospace'
            executable.write_text('#!/bin/sh\nprintf "%s\\n" "$*"\n')
            executable.chmod(0o755)
            script = root/'guard.zsh'
            source = (ROOT/'aerospace-mouse-follow.sh').read_text()
            source = source.replace('marker="$HOME/.local/state/dotfiles-wm/bar-mouse-suppressed"', f'marker="{marker}"')
            script.write_text(source)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'])
            for live in (True, False):
                marker.write_text(f'{os.getpid()} {time.time() + (3 if live else -3)}\n')
                result = subprocess.check_output(['/bin/zsh',str(script),'window-force-center'],env=env,text=True)
                self.assertEqual(result.strip(), '' if live else 'move-mouse window-force-center')
            marker.unlink()
            self.assertEqual(subprocess.check_output(['/bin/zsh',str(script),'monitor-lazy-center'],env=env,text=True).strip(),
                             'move-mouse monitor-lazy-center')


if __name__ == '__main__': unittest.main()
