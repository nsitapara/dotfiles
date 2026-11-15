"""The hover provider must follow the daemon, not a concurrent IPC client."""
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

LAUNCHER = Path(__file__).resolve().parents[1] / "sketchybar-hover/run.py"


class HoverLauncherTests(unittest.TestCase):
    def test_helper_follows_daemon_when_client_pid_is_lower_after_pid_wrap(self):
        for clients in ([], [120, 35000]):
            with self.subTest(clients=clients), tempfile.TemporaryDirectory() as home:
                binary = Path(home) / ".cache/dotfiles/sketchybar-hover/sbar-hover"
                binary.parent.mkdir(parents=True)
                binary.touch()
                # Skip compilation: this test exercises process selection only.
                os.utime(binary, (4102444800, 4102444800))

                def pgrep(arguments, **kwargs):
                    self.assertEqual(arguments[0], "pgrep")
                    # macOS excludes ancestors by default and sorts normal
                    # matches by PID. -o instead selects the earliest start.
                    matches = [(pid, 2) for pid in clients]
                    if "-a" in arguments:
                        matches.append((39136, 1))  # daemon is the Lua launcher's ancestor
                    if "-o" in arguments:
                        matches = [min(matches, key=lambda item: item[1])]
                    return "".join(str(pid) + "\n" for pid, _ in sorted(matches))

                with patch.dict(os.environ, HOME=home), \
                     patch("sys.argv", [str(LAUNCHER)]), \
                     patch("subprocess.check_output", side_effect=pgrep), \
                     patch("subprocess.run"), patch("shutil.which", return_value="/bin/sketchybar"), \
                     patch("signal.signal"), patch("signal.alarm"), patch("os.execv") as execute:
                    runpy.run_path(str(LAUNCHER), run_name="__main__")
                self.assertEqual(execute.call_args.args[1][2], "39136")


if __name__ == "__main__":
    unittest.main()
