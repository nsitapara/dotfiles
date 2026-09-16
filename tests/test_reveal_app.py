"""Exercise app recovery with fake desktop commands and the real JSON filter."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RevealAppTests(unittest.TestCase):
    def run_recovery(self, windows, pid='42', malformed=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'windows').write_text('[' if malformed else json.dumps(windows))
            (root / 'yabai').write_text('''#!/bin/bash
if [ "$2" = query ]; then cat "$FIXTURE/windows"; else echo "yabai $*" >> "$FIXTURE/calls"; fi
''')
            (root / 'osascript').write_text('''#!/bin/bash
echo unhide >> "$FIXTURE/calls"
''')
            for name in ['yabai', 'osascript']:
                (root / name).chmod(0o755)
            result = subprocess.run(['/bin/bash', str(ROOT / 'yabai/.config/yabai/scripts/reveal-app.sh'), pid],
                                    env={**os.environ, 'PATH': directory + ':' + os.environ['PATH'],
                                         'FIXTURE': directory}, capture_output=True, text=True)
            calls = (root / 'calls').read_text().splitlines() if (root / 'calls').exists() else []
            return result, calls

    def test_visible_app_needs_no_recovery(self):
        result, calls = self.run_recovery([{'id': 1, 'pid': 42, 'is-hidden': False}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])

    def test_hidden_and_minimized_windows_are_restored(self):
        result, calls = self.run_recovery([
            {'id': 1, 'pid': 42, 'is-hidden': True, 'is-minimized': True},
            {'id': 2, 'pid': 42, 'is-minimized': True},
            {'id': 3, 'pid': 99, 'is-hidden': True, 'is-minimized': True},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['unhide', 'yabai -m window --deminimize 1',
                                'yabai -m window --focus 1', 'yabai -m window --deminimize 2',
                                'yabai -m window --focus 2'])

    def test_minimized_visible_app_skips_applescript(self):
        result, calls = self.run_recovery([{'id': 1, 'pid': 42, 'is-minimized': True}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['yabai -m window --deminimize 1', 'yabai -m window --focus 1'])

    def test_windowless_app_keeps_unhide_fallback(self):
        result, calls = self.run_recovery([])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['unhide'])

    def test_invalid_input_never_acts(self):
        for pid, malformed in [('not-a-pid', False), ('42', True)]:
            result, calls = self.run_recovery([], pid, malformed)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
