"""Desktop setup retries transient Mission Control dismissal without real UI."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "yabai/.config/yabai/scripts"


@unittest.skipUnless(sys.platform == "darwin", "uses macOS lockf")
class EnsureSpacesTests(unittest.TestCase):
    def test_retry_only_transient_mission_control_failure(self):
        cases = [
            ("OK Created 0 missing and removed 3 surplus desktops.", False, 1, True),
            ("ERROR No thumbnail 5 for desktop 6 on display 1: no mc.spaces.list", False, 2, True),
            ("ERROR Mission Control did not expose its Accessibility controls.", False, 2, True),
            ("ERROR No thumbnail 5 for desktop 6 on display 1: no mc.spaces.list", True, 2, False),
            ("ERROR Enable Dotfiles Spaces in Accessibility", False, 1, False),
            ("ERROR Monitor layout changed; retry after it settles.", False, 1, False),
        ]
        for message, persistent, attempts, succeeds in cases:
            with self.subTest(message=message, persistent=persistent), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                shutil.copy2(SCRIPTS / "ensure-spaces.sh", root / "ensure-spaces.sh")
                for name, body in {
                    "build-spaces-helper.sh": "exit 0",
                    "display-layout.sh": "echo '[]'",
                    "spaces.sh": 'touch "$TEST_ROOT/labelled"',
                    "sleep": "exit 0",
                    "yabai": "exit 0",
                }.items():
                    script = root / name
                    script.write_text("#!/bin/bash\n" + body + "\n")
                    script.chmod(0o755)
                opener = root / "open"
                opener.write_text("#!" + sys.executable + "\n" + r'''
import os, pathlib, sys
root = pathlib.Path(os.environ["TEST_ROOT"])
counter = root / "attempts"
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
message = os.environ["TEST_MESSAGE"]
if n > 1 and os.environ["TEST_PERSISTENT"] != "1":
    message = "OK Created 0 missing and removed 3 surplus desktops."
pathlib.Path(sys.argv[-2]).write_text(message + "\n")
''')
                opener.chmod(0o755)
                env = dict(os.environ, HOME=folder, TMPDIR=folder, TEST_ROOT=folder,
                           TEST_MESSAGE=message, TEST_PERSISTENT=str(int(persistent)),
                           PATH=str(root) + ":/opt/homebrew/bin:/usr/bin:/bin")
                result = subprocess.run(["/bin/bash", str(root / "ensure-spaces.sh")],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                self.assertEqual(int((root / "attempts").read_text()), attempts)
                self.assertEqual((root / "labelled").exists(), succeeds)


if __name__ == "__main__":
    unittest.main()
