"""Exercise profile transitions without touching live configs or displays.

Run on macOS: python3 tests/test_display_mode_switcher.py
The macOS lockf command is real; desktop apps and Stow are simulated.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ["DISPLAY_TEST_DIR"])
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = root / "mock.json"
state = json.loads(state_path.read_text())
def save():
    state_path.write_text(json.dumps(state))
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps([name] + args) + "\n")
if name == "system_profiler":
    if state.get("detection_failure"):
        sys.exit(1)
    counts = state["counts"]
    count = counts.pop(0) if len(counts) > 1 else counts[0]
    save()
    print("Resolution: 2560 x 1440\n" * count)
elif name == "readlink":
    app = "aerospace" if "aerospace.toml" in args[-1] else "sketchybar"
    print(str(root / state[app] / ".config" / app / pathlib.Path(args[-1]).name))
elif name == "pgrep":
    sys.exit(0)
elif name == "stow":
    if state.get("stow_failure"):
        sys.exit(1)
    time.sleep(state.get("stow_delay", 0))
    if args[0] != "-D":
        app = "aerospace" if args[0].startswith("aerospace") else "sketchybar"
        state[app] = args[0]
        save()
elif name == "sketchybar":
    if args[0] == "--reload":
        if state.get("reload_failure"):
            sys.exit(1)
        if not state.get("load_failure"):
            state["loaded"] = "docked" if state["sketchybar"].endswith("-docked") else "non-docked"
            save()
    elif args == ["--query", "displays"]:
        print(json.dumps(state.get("layout", [{"arrangement-id": 1}])))
    elif args == ["--query", "display_mode"]:
        print(json.dumps({"label": {"value": state["loaded"]}}))
elif name == "sleep":
    pass
elif name != "aerospace":
    raise AssertionError((name, args))
'''


@unittest.skipUnless(sys.platform == "darwin", "requires macOS lockf")
class DisplayModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="display-mode-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.script = self.path / "switch-display-mode.sh"
        shutil.copy2(ROOT / self.script.name, self.script)
        self.bin = self.path / "bin"
        self.bin.mkdir()
        for name in ("system_profiler", "readlink", "pgrep", "stow", "sketchybar", "aerospace", "sleep"):
            command = self.bin / name
            command.write_text(f"#!{sys.executable}\n" + MOCK)
            command.chmod(0o755)
        self.env = dict(os.environ, TMPDIR=str(self.path), DISPLAY_TEST_DIR=str(self.path))
        self.env["PATH"] = f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin"
        self.state_file = self.path / ".display-mode-state"
        self.mock_file = self.path / "mock.json"
        self.configure()

    def configure(self, mode="docked", counts=None, **overrides):
        suffix = "-docked" if mode == "docked" else ""
        state = dict(counts=counts or [1], aerospace="aerospace" + suffix,
                     sketchybar="sketchybar" + suffix, loaded=mode)
        state.update(overrides)
        self.mock_file.write_text(json.dumps(state))
        self.state_file.write_text(mode + "\n")

    def run_switch(self, success=True):
        result = subprocess.run(["/bin/bash", str(self.script)], env=self.env,
                                capture_output=True, text=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def calls(self, name):
        return [call for line in (self.path / "calls.jsonl").read_text().splitlines()
                if (call := json.loads(line))[0] == name]

    def assert_profile(self, mode):
        self.assertEqual(self.state_file.read_text().strip(), mode)
        self.assertEqual(json.loads(self.mock_file.read_text())["loaded"], mode)

    def test_unplug_loads_new_path_and_repeated_runs_are_noops(self):
        self.run_switch()
        self.assert_profile("non-docked")
        reloads = [c for c in self.calls("sketchybar") if c[1] == "--reload"]
        self.assertEqual(reloads, [["sketchybar", "--reload",
                                   str(Path.home() / ".config/sketchybar/sketchybarrc")]])
        before = self.calls("stow")
        self.run_switch()
        self.run_switch()
        self.assertEqual(self.calls("stow"), before)

    def test_repeated_dock_undock_cycles(self):
        for count, mode in [(1, "non-docked"), (2, "docked")] * 3:
            state = json.loads(self.mock_file.read_text())
            state["counts"] = [count]
            self.mock_file.write_text(json.dumps(state))
            self.run_switch()
            self.assert_profile(mode)

    def test_sketchybar_symlink_desync_is_repaired(self):
        self.run_switch()
        self.configure(mode="non-docked", sketchybar="sketchybar-docked")
        self.run_switch()
        self.assertEqual(json.loads(self.mock_file.read_text())["sketchybar"], "sketchybar")

    def test_stale_running_profile_is_repaired(self):
        self.run_switch()
        self.configure(mode="non-docked", loaded="docked")
        self.run_switch()
        self.assert_profile("non-docked")
        self.assertTrue(self.calls("stow"))

    def test_no_displays_leaves_current_config_untouched(self):
        self.configure(counts=[0])
        self.run_switch(success=False)
        self.assertEqual(self.calls("stow"), [])
        self.assert_profile("docked")

    def test_failed_detection_leaves_current_config_untouched(self):
        self.configure(detection_failure=True)
        self.run_switch(success=False)
        self.assertEqual(self.calls("stow"), [])
        self.assert_profile("docked")

    def test_transient_display_counts_must_settle(self):
        self.configure(counts=[0, 2, 1, 1])
        self.run_switch()
        self.assertEqual(len(self.calls("system_profiler")), 4)
        self.assert_profile("non-docked")

    def test_unstable_counts_leave_current_config_untouched(self):
        self.configure(counts=[1, 2, 1, 2, 1])
        self.run_switch(success=False)
        self.assertEqual(self.calls("stow"), [])
        self.assert_profile("docked")

    def test_failed_reload_retries_without_recording_success(self):
        self.configure(reload_failure=True)
        self.run_switch(success=False)
        self.assert_profile("docked")
        state = json.loads(self.mock_file.read_text())
        state["reload_failure"] = False
        self.mock_file.write_text(json.dumps(state))
        self.run_switch()
        self.assert_profile("non-docked")

    def test_successful_command_with_failed_lua_load_is_not_success(self):
        self.configure(load_failure=True)
        self.run_switch(success=False)
        self.assert_profile("docked")

    def test_stow_failure_does_not_reload_or_record_success(self):
        self.configure(stow_failure=True)
        self.run_switch(success=False)
        self.assertFalse(any(c[1] == "--reload" for c in self.calls("sketchybar")))
        self.assert_profile("docked")

    def test_same_display_count_with_changed_layout_refreshes_assignments(self):
        self.configure(counts=[2])
        self.run_switch()
        before = len(self.calls("stow"))
        state = json.loads(self.mock_file.read_text())
        state["layout"] = [{"arrangement-id": 2, "frame": {"x": 2560}}]
        self.mock_file.write_text(json.dumps(state))
        self.run_switch()
        self.assertGreater(len(self.calls("stow")), before)
        self.assert_profile("docked")

    def test_overlapping_invocations_only_switch_once(self):
        self.configure(stow_delay=0.1)
        first = subprocess.Popen(["/bin/bash", str(self.script)], env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.path / "calls.jsonl").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.run_switch()
            out, err = first.communicate(timeout=15)
            self.assertEqual(first.returncode, 0, out + err)
        finally:
            if first.poll() is None:
                first.kill()
                first.communicate()
        self.assertEqual(len(self.calls("stow")), 6)
        self.assert_profile("non-docked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
