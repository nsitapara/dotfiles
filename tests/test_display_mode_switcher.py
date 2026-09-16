"""Exercise profile transitions without touching live configs or displays.

Run on macOS: python3 tests/test_display_mode_switcher.py
The macOS lockf command is real; desktop apps and Stow are simulated.
"""

import json
import os
import re
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
    print(state.get("diagnostic_text", ""))
elif name == "readlink":
    app = "aerospace" if "aerospace.toml" in args[-1] else "sketchybar"
    print(str(root / state[app] / ".config" / app / pathlib.Path(args[-1]).name))
elif name == "pgrep":
    sys.exit(1 if args[-1] == "sketchybar" and state.get("bar_stopped") else 0)
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
        print(json.dumps({"icon": {"value": ""}, "label": {"value": state["loaded"], "background": {"image": {"value": "(null)"}}}}, indent=2))
elif name == "display-layout.sh":
    print(json.dumps(state["plan"]))
elif name == "display-profile.sh":
    if state.get("service_test") and state.get("service_ticks") == 1:
        sys.exit(1)
elif name == "wm.sh":
    state["manager_starts"] = state.get("manager_starts", 0) + 1
    state["yabai_trial"] = args[0] == "yabai"
    save()
elif name == "launchctl":
    sys.exit(0 if state.get("yabai_trial") and args[-1] == "local.dotfiles.yabai" else 1)
elif name == "sleep":
    if args == ["30"] and state.get("service_test"):
        state["service_ticks"] = state.get("service_ticks", 0) + 1
        # Simulate a manual switch to AeroSpace after the first failed check.
        if state["service_ticks"] == 2:
            state["yabai_trial"] = False
        save()
        if state["service_ticks"] > 2:
            sys.exit(1)
elif name == "aerospace" and args[0] == "list-workspaces":
    print(state.get("assignments", ""))
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
        for name in ("system_profiler", "readlink", "pgrep", "stow", "sketchybar", "aerospace", "sleep", "launchctl"):
            command = self.bin / name
            command.write_text(f"#!{sys.executable}\n" + MOCK)
            command.chmod(0o755)
        self.home = self.path / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), TMPDIR=str(self.path), DISPLAY_TEST_DIR=str(self.path))
        self.env["PATH"] = f"{self.bin}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        self.state_file = self.path / ".display-mode-state"
        self.mock_file = self.path / "mock.json"
        helpers = self.path / "yabai/.config/yabai/scripts"
        helpers.mkdir(parents=True)
        for name in ["display-layout.sh", "display-profile.sh"]:
            file = helpers / name
            file.write_text(f"#!{sys.executable}\n" + MOCK)
            file.chmod(0o755)
        self.configure()

    def test_service_propagates_startup_failure_before_display_checks(self):
        wm = self.path / "wm.sh"
        wm.write_text('#!/bin/bash\nprintf "%s" "$1" > "$DISPLAY_TEST_DIR/login-manager"\nexit 7\n')
        wm.chmod(0o755)
        for manager in ("yabai", "aerospace", "rift"):
            with self.subTest(manager=manager):
                result = subprocess.run([str(self.script), "--service", manager], env=self.env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 7)
                self.assertEqual((self.path / "login-manager").read_text(), manager)
                self.assertFalse(Path(str(self.state_file) + ".lock").exists())

    def test_service_rejects_missing_or_invalid_manager(self):
        for args in (["--service"], ["--service", "other"], ["--service", "yabai", "extra"]):
            with self.subTest(args=args):
                result = subprocess.run([str(self.script), *args], env=self.env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 64)

    def test_service_starts_manager_once_without_display_checks(self):
        self.configure(counts=[2])
        wm = self.path / "wm.sh"
        wm.write_text(f"#!{sys.executable}\n" + MOCK)
        wm.chmod(0o755)
        result = subprocess.run([str(self.script), "--service", "yabai"], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(self.mock_file.read_text())
        self.assertEqual(state["manager_starts"], 1)
        self.assertNotIn("service_ticks", state)
        calls = [json.loads(line) for line in (self.path / "calls.jsonl").read_text().splitlines()]
        self.assertFalse(any(c[0] in ("display-profile.sh", "display-layout.sh") for c in calls))

    def configure(self, mode="docked", counts=None, **overrides):
        suffix = "-docked" if mode == "docked" else ""
        state = dict(counts=counts or [1], aerospace="aerospace" + suffix,
                     sketchybar="sketchybar" + suffix, loaded=mode)
        state["plan"] = [dict(id=1,index=1,workspaces=[1,2,3,4,5,6])]
        state.update(overrides)
        self.mock_file.write_text(json.dumps(state))
        self.state_file.write_text(mode + "\n")
        canonical = json.dumps(state["plan"], sort_keys=True, separators=(",",":"))
        signature = subprocess.check_output(["cksum"], input="\n"+canonical+"\n", text=True)
        Path(str(self.state_file)+".workspaces").write_text(signature)

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
                                   str(self.home / ".config/sketchybar/sketchybarrc")]])
        before = self.calls("stow")
        self.run_switch()
        self.run_switch()
        self.assertEqual(self.calls("stow"), before)

    def test_yabai_trial_delegates_without_changing_aerospace(self):
        self.configure(yabai_trial=True)
        self.run_switch()
        self.assertEqual(len(self.calls("display-profile.sh")), 1)
        self.assertEqual(self.calls("system_profiler"), [])
        self.assertEqual(self.calls("stow"), [])
        self.assertEqual(self.calls("sketchybar"), [])
        self.assert_profile("docked")

    def test_shared_three_screen_plan_moves_only_incorrect_assignments(self):
        plan = [dict(id=3,index=1,workspaces=[7,8,9]),
                dict(id=1,index=2,workspaces=[1,3,5]),
                dict(id=2,index=3,workspaces=[2,4,6])]
        self.configure(counts=[3],plan=plan,assignments="1|2\n3|2\n5|2")
        Path(str(self.state_file)+".workspaces").unlink()
        self.run_switch()
        moves = [c for c in self.calls("aerospace") if c[1] == "move-workspace-to-monitor"]
        self.assertEqual(moves, [["aerospace","move-workspace-to-monitor","--workspace",str(w),str(m)]
                                 for m,ws in [(1,[7,8,9]),(3,[2,4,6])] for w in ws])
        self.assertEqual(json.loads((self.home/".local/state/dotfiles-wm/display-layout.json").read_text()),plan)
        self.run_switch()
        self.assertEqual(moves,[c for c in self.calls("aerospace") if c[1] == "move-workspace-to-monitor"])

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
        before = self.calls("stow")
        self.run_switch()
        self.assert_profile("non-docked")
        self.assertEqual(self.calls("stow"), before)

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
        self.assertEqual(len(self.calls("stow")), before)
        self.assertEqual(len([c for c in self.calls("sketchybar") if c[1] == "--reload"]), 1)
        self.assert_profile("docked")

    def test_diagnostic_changes_do_not_reload(self):
        self.configure(counts=[2])
        self.run_switch()
        for text in ["UI Looks like: 2560 x 1440 @ 74.99Hz", "UI Looks like: 2560 x 1440 @ 75.00Hz"]:
            state = json.loads(self.mock_file.read_text())
            state["diagnostic_text"] = text
            self.mock_file.write_text(json.dumps(state))
            self.run_switch()
        self.assertEqual(self.calls("stow"), [])
        self.assertFalse(any(c[1] == "--reload" for c in self.calls("sketchybar")))

    def test_bar_temporarily_absent_does_not_invalidate_layout(self):
        self.configure(counts=[2])
        self.run_switch()
        snapshot = Path(str(self.state_file) + ".displays").read_text()
        for stopped in [True, False, True, False]:
            state = json.loads(self.mock_file.read_text())
            state["bar_stopped"] = stopped
            self.mock_file.write_text(json.dumps(state))
            self.run_switch()
            self.assertEqual(Path(str(self.state_file) + ".displays").read_text(), snapshot)
        self.assertEqual(self.calls("stow"), [])
        self.assertFalse(any(c[1] == "--reload" for c in self.calls("sketchybar")))

    def test_unavailable_marker_waits_without_reset(self):
        self.configure(counts=[2], loaded="")
        self.run_switch()
        self.assertEqual(self.calls("stow"), [])
        self.assertFalse(any(c[1] == "--reload" for c in self.calls("sketchybar")))

    def test_missing_state_does_not_reset_matching_profile(self):
        self.configure(counts=[2])
        self.state_file.unlink()
        self.run_switch()
        self.run_switch()
        self.assertEqual(self.calls("stow"), [])
        self.assertFalse(any(c[1] == "--reload" for c in self.calls("sketchybar")))

    def test_focus_callback_accepts_aerospace_trailing_newline(self):
        lua = "/opt/homebrew/opt/lua@5.4/bin/lua5.4"
        for profile in ["sketchybar", "sketchybar-docked"]:
            source = (ROOT / profile / ".config/sketchybar/items/spaces.lua").read_text()
            body = re.search(r'-- seed the focus highlight.*?function\(result\)(.*?)\nend\)',
                             source, re.S).group(1)
            program = "local focused; function set_focus(n) focused = n end\n"
            program += "local function callback(result)\n" + body + "\nend\n"
            program += 'callback("3\\n"); assert(focused == 3); callback(""); assert(focused == nil)'
            result = subprocess.run([lua, "-"], input=program, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

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
