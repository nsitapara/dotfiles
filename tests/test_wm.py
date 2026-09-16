"""Test switching and failure recovery with fake desktop commands.

No processes, preferences, packages, or live configuration links are changed.
Run: python3 -m unittest discover -s tests -p 'test_wm.py' -v
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ShortcutTests(unittest.TestCase):
    @staticmethod
    def skhd_bindings():
        keypad = dict(zip(["0x53","0x54","0x55","0x56","0x57","0x58","0x59","0x5B","0x5C"],
                          [f"keypad{i}" for i in range(1,10)]))
        keypad.update({"0x18":"equal", "0x1B":"minus", "0x2B":"comma"})
        result = set()
        for raw in (ROOT / "skhd/.config/skhd/skhdrc").read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "::")):
                continue
            # Include modal bindings: Raycast launch keys should still pass through.
            line = line.split("<", 1)[-1].strip()
            lhs = re.split(r"[:;]", line, maxsplit=1)[0].strip()
            parts = re.split(r"\s*[+\-]\s*", lhs)
            parts[-1] = keypad.get(parts[-1], parts[-1])
            result.add(tuple(sorted(p.lower() for p in parts[:-1])) + (parts[-1].lower(),))
        return result

    def test_raycast_shortcuts_from_screenshot_remain_available(self):
        reserved = {("cmd", "shift", key) for key in "cegbpsvzd"}
        reserved.update({("cmd", "return"), ("alt", "shift", "m"), ("cmd", "ctrl", "space")})
        self.assertFalse(reserved & self.skhd_bindings())
        # Capture modes would consume otherwise unbound Raycast shortcuts.
        for line in (ROOT / "skhd/.config/skhd/skhdrc").read_text().splitlines():
            if line.startswith("::"):
                self.assertNotIn("@", line.split(":", 3)[2])

    def test_trial_does_not_claim_new_global_keys_from_raycast(self):
        aerospace = tomllib.loads((ROOT / "aerospace-docked/.config/aerospace/aerospace.toml").read_text())
        single = tomllib.loads((ROOT / "aerospace/.config/aerospace/aerospace.toml").read_text())
        self.assertEqual(single["mode"], aerospace["mode"],
                         "AeroSpace shortcuts must not change when a monitor is connected")
        def normalize(parts):
            return tuple(sorted(p.lower() for p in parts[:-1])) + (parts[-1].lower(),)
        current = {normalize(key.split("-")) for key in aerospace["mode"]["main"]["binding"]}
        keypad = dict(zip(["0x53","0x54","0x55","0x56","0x57","0x58","0x59","0x5B","0x5C"],
                          [f"keypad{i}" for i in range(1,10)]))
        keypad.update({"0x18":"equal", "0x1B":"minus", "0x2B":"comma"})
        for raw in (ROOT / "skhd/.config/skhd/skhdrc").read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "::")) or "<" in line:
                continue
            lhs = re.split(r"[:;]", line, maxsplit=1)[0].strip()
            parts = re.split(r"\s*[+\-]\s*", lhs)
            parts[-1] = keypad.get(parts[-1], parts[-1])
            self.assertIn(normalize(parts), current, f"New global shortcut: {lhs}")


MOCK = r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ["WM_TEST_ROOT"])
statefile = root / "mock.json"
state = json.loads(statefile.read_text())
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps([name] + args) + "\n")
def save(): statefile.write_text(json.dumps(state))
if name == "uname": print("Darwin")
elif name == "pgrep": sys.exit(0 if args[-1] in state["running"] else 1)
elif name == "defaults":
    key = args[2]
    if args[0] == "read":
        if key not in state["prefs"]: sys.exit(1)
        print(state["prefs"][key])
    elif args[0] == "write": state["prefs"][key] = 0 if args[-1] in ("false", "0") else 1; save()
    elif args[0] == "delete": state["prefs"].pop(key, None); save()
elif name == "readlink":
    pkg = "skhd" if "skhdrc" in args[-1] else "yabai"
    print(root / pkg / ".config" / pkg / (pkg + "rc"))
elif name == "launchctl":
    if args[0] == "list":
        sys.exit(0 if args[1] in state["jobs"] else 1)
    if args[0] == "remove":
        job = args[1]
        state["jobs"].remove(job)
        app = job.split(".")[-1]
        if app in state["running"]: state["running"].remove(app)
        save()
    elif args[0] == "submit":
        job = args[args.index("-l") + 1]
        app = job.split(".")[-1]
        assert "AeroSpace" not in state["running"], "Started a second WM!"
        state["jobs"].append(job)
        if state.get("fail_start") != app: state["running"].append(app)
        if app == "yabai" and not state.get("config_failure"):
            for arg in args:
                if arg.startswith("DOTFILES_YABAI_READY="):
                    pathlib.Path(arg.split("=",1)[1]).touch()
        if app == "skhd" and state.get("skhd_parse_failure"):
            with pathlib.Path(args[args.index("-e") + 1]).open("a") as log:
                log.write("#9:4 expected identifier\n")
        save()
elif name == "yabai":
    if args == ["--version"]: print("yabai-v" + state.get("version", "7.1.25"))
    elif args[:3] == ["-m", "query", "--spaces"]:
        if "yabai" not in state["running"]: sys.exit(1)
        print(json.dumps(state["spaces"]))
    elif args[:3] == ["-m", "query", "--displays"]: print(json.dumps(state["displays"]))
    elif args[:2] == ["-m", "space"] and args[3] == "--label":
        for space in state["spaces"]:
            if space["index"] == int(args[2]): space["label"] = args[4] if len(args) > 4 else ""
        save()
elif name == "skhd": print("skhd-v0.3.9")
elif name == "osascript":
    if not state.get("quit_failure") and "AeroSpace" in state["running"]: state["running"].remove("AeroSpace")
    save()
elif name == "open":
    assert "yabai" not in state["running"] and "skhd" not in state["running"], "Unsafe restore!"
    if "AeroSpace" not in state["running"]: state["running"].append("AeroSpace")
    save()
elif name == "ioreg":
    if state.get("secure_input", 0) > 0:
        state["secure_input"] -= 1; save(); print('"kCGSSessionSecureInputPID"=2102')
elif name in ("sleep", "sketchybar", "stow", "brew"): pass
else: raise AssertionError((name, args))
'''


@unittest.skipUnless(sys.platform == "darwin", "requires macOS descriptor lockf")
class WmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wm-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        shutil.copy2(ROOT / "wm.sh", self.path / "wm.sh")
        helpers = self.path / "yabai/.config/yabai/scripts"
        helpers.mkdir(parents=True)
        for name in ("ensure-spaces.sh", "build-spaces-helper.sh"):
            helper = helpers / name
            helper.write_text('#!/bin/bash\nexit "${WM_TEST_SETUP_EXIT:-0}"\n')
            helper.chmod(0o755)
        (helpers / "spaces.sh").write_text('#!/bin/bash\necho "Ready: ws1"\n')
        (helpers / "spaces.sh").chmod(0o755)
        profile = helpers / "display-profile.sh"
        profile.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$WM_TEST_ROOT/profile-args"\n'
                           'exit "${WM_TEST_PROFILE_EXIT:-0}"\n')
        profile.chmod(0o755)
        (self.path / "switch-display-mode.sh").write_text('#!/bin/bash\ntouch "$WM_TEST_ROOT/switched"\nexit 0\n')
        (self.path / "switch-display-mode.sh").chmod(0o755)
        self.bin = self.path / "bin"
        self.bin.mkdir()
        for name in ("uname", "pgrep", "defaults", "readlink", "launchctl", "yabai", "skhd",
                     "osascript", "open", "sleep", "sketchybar", "stow", "brew", "ioreg"):
            file = self.bin / name
            file.write_text(f"#!{sys.executable}\n" + MOCK)
            file.chmod(0o755)
        self.env = dict(os.environ, WM_TEST_ROOT=str(self.path), TMPDIR=str(self.path),
                        DOTFILES_WM_STATE_DIR=str(self.path / "state"))
        self.env["PATH"] = str(self.bin) + ":" + os.environ["PATH"]
        self.state = dict(running=["AeroSpace", "sketchybar"], jobs=[],
                          prefs={"spans-displays": 0, "mru-spaces": 0},
                          spaces=[], displays=[])
        self.save()

    def save(self):
        (self.path / "mock.json").write_text(json.dumps(self.state))

    def refresh(self):
        self.state = json.loads((self.path / "mock.json").read_text())

    def calls(self, name):
        return [c for line in (self.path / "calls.jsonl").read_text().splitlines()
                if (c := json.loads(line))[0] == name]

    def run_wm(self, command, success=True, *args):
        result = subprocess.run(["/bin/bash", str(self.path / "wm.sh"), command, *args],
                                env=self.env, capture_output=True, text=True, timeout=30)
        self.refresh()
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_switch_round_trip_and_repeated_start(self):
        self.run_wm("yabai")
        self.assertEqual(set(self.state["running"]), {"yabai", "skhd", "sketchybar"})
        self.run_wm("yabai")
        self.assertEqual(len([c for c in self.calls("launchctl") if c[1] == "submit"]), 2)
        self.run_wm("aerospace")
        self.assertEqual(set(self.state["running"]), {"AeroSpace", "sketchybar"})
        self.assertEqual(self.state["jobs"], [])
        self.assertFalse(any("--start-service" in c for c in self.calls("yabai") + self.calls("skhd")))

    def test_start_applies_profile_without_an_earlier_bar_reload(self):
        self.run_wm("yabai")
        self.assertEqual((self.path / "profile-args").read_text().strip(), "--force")
        self.assertEqual(self.calls("sketchybar"), [])
        self.assertFalse((self.path / "switched").exists())

    def test_profile_failure_rolls_back_startup(self):
        self.env["WM_TEST_PROFILE_EXIT"] = "1"
        self.run_wm("yabai", success=False)
        self.assertEqual(self.state["jobs"], [])
        self.assertEqual(set(self.state["running"]), {"AeroSpace", "sketchybar"})

    def test_disabled_separate_spaces_does_not_quit_aerospace(self):
        self.state["prefs"]["spans-displays"] = 1
        self.save()
        self.run_wm("yabai", success=False)
        self.assertEqual(self.calls("osascript"), [])
        self.assertEqual(self.state["jobs"], [])

    def test_old_yabai_does_not_quit_aerospace(self):
        self.state["version"] = "7.1.18"
        self.save()
        self.run_wm("yabai", success=False)
        self.assertEqual(self.calls("osascript"), [])

    def test_skhd_failure_restores_aerospace(self):
        self.state["fail_start"] = "skhd"
        self.save()
        self.run_wm("yabai", success=False)
        self.assertEqual(self.state["jobs"], [])
        self.assertEqual(set(self.state["running"]), {"AeroSpace", "sketchybar"})

    def test_desktop_setup_failure_keeps_yabai_with_existing_desktops(self):
        self.env["WM_TEST_SETUP_EXIT"] = "1"
        result = self.run_wm("yabai")
        self.assertIn("Desktop creation unavailable", result.stderr)
        self.assertEqual(set(self.state["running"]), {"yabai", "skhd", "sketchybar"})

    def test_waits_for_secure_keyboard_entry_before_starting_skhd(self):
        self.state["secure_input"] = 3
        self.save()
        self.run_wm("yabai")
        self.assertIn("skhd", self.state["running"])
        self.assertEqual(len(self.calls("ioreg")), 4)

    def test_skhd_parser_failure_restores_aerospace_even_while_process_runs(self):
        self.state["skhd_parse_failure"] = True
        self.save()
        result = self.run_wm("yabai", success=False)
        self.assertIn("could not load its shortcuts", result.stderr)
        self.assertEqual(self.state["jobs"], [])
        self.assertIn("AeroSpace", self.state["running"])

    def test_old_skhd_errors_do_not_fail_new_start(self):
        (self.path / "state").mkdir()
        (self.path / "state/skhd.err.log").write_text("#9:4 expected identifier\n")
        self.run_wm("yabai")
        self.assertIn("skhd", self.state["running"])

    def test_config_failure_restores_aerospace(self):
        self.state["config_failure"] = True
        self.save()
        self.run_wm("yabai", success=False)
        self.assertEqual(self.state["jobs"], [])
        self.assertIn("AeroSpace", self.state["running"])

    def test_quit_failure_does_not_start_yabai(self):
        self.state["quit_failure"] = True
        self.save()
        self.run_wm("yabai", success=False)
        self.assertEqual(self.state["jobs"], [])
        self.assertFalse(any(c[1] == "submit" for c in self.calls("launchctl")))

    def test_existing_external_skhd_is_preserved(self):
        self.state["running"].append("skhd")
        self.save()
        self.run_wm("yabai", success=False)
        self.assertIn("skhd", self.state["running"])
        self.assertEqual(self.calls("osascript"), [])

    def test_profile_pin_applies_immediately(self):
        pin = self.path / "state/display-profile.pin"
        self.run_wm("profile", True, "docked")
        self.assertEqual(pin.read_text().strip(), "docked")
        self.assertTrue((self.path / "switched").exists())
        self.assertEqual(self.run_wm("profile").stdout.split()[0], "docked")
        self.run_wm("profile", False, "bogus")
        self.assertEqual(pin.read_text().strip(), "docked")
        self.run_wm("profile", True, "auto")
        self.assertFalse(pin.exists())
        self.assertEqual(self.run_wm("profile").stdout.split()[0], "auto")

    def test_prepare_is_repeatable_and_restores_absent_values(self):
        self.state["prefs"] = {"spans-displays": 1}
        self.save()
        self.run_wm("prepare")
        self.run_wm("prepare")
        self.assertEqual(self.state["prefs"], {"spans-displays": 0, "mru-spaces": 0})
        self.run_wm("restore-preferences")
        self.assertEqual(self.state["prefs"], {"spans-displays": 1})

    def native_spaces(self, counts):
        self.state["running"].append("yabai")
        self.state["displays"] = [dict(index=i+1, frame=dict(x=i*1920,y=0)) for i in range(len(counts))]
        for display, count in enumerate(counts,1):
            for _ in range(count):
                self.state["spaces"].append(dict(index=len(self.state["spaces"])+1,
                    display=display, label="", **{"is-native-fullscreen":False}))
        self.save()

    def run_spaces(self, success=True, plan=None, check=False):
        if plan is None:
            plan = ([dict(index=1,workspaces=[1,2,3,4,5,6])]
                    if len(self.state["displays"]) == 1 else
                    [dict(index=1,workspaces=[1,3,5]),dict(index=2,workspaces=[2,4,6])])
        plan_path = self.path / "plan.json"
        plan_path.write_text(json.dumps(plan))
        result = subprocess.run(["/bin/bash", str(ROOT / "yabai/.config/yabai/scripts/spaces.sh"), "--plan", str(plan_path)] + (["--check"] if check else []),
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.refresh()
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_label_check_rejects_missing_labels_without_changing_spaces(self):
        self.native_spaces([3,3])
        self.run_spaces(success=False, check=True)
        self.assertTrue(all(s['label'] == '' for s in self.state['spaces']))
        self.assertFalse(any('--label' in c for c in self.calls('yabai')))
        self.assertEqual(self.calls('sketchybar'), [])
        self.run_spaces()
        self.assertEqual(self.calls('sketchybar'), [['sketchybar', '--trigger', 'yabai_windows_changed']])
        before = len([c for c in self.calls('yabai') if '--label' in c])
        self.run_spaces(check=True)
        self.assertEqual(len([c for c in self.calls('yabai') if '--label' in c]), before)

    def test_six_laptop_desktops_are_labelled(self):
        self.native_spaces([6])
        self.run_spaces()
        self.assertEqual([s["label"] for s in self.state["spaces"]], [f"ws{i}" for i in range(1,7)])

    def test_two_monitors_keep_odd_even_shortcuts(self):
        self.native_spaces([3,3])
        self.run_spaces()
        self.assertEqual([s["label"] for s in self.state["spaces"]], ["ws1","ws3","ws5","ws2","ws4","ws6"])
        before = self.calls("yabai")
        self.run_spaces()
        self.assertEqual(len([c for c in self.calls("yabai") if "--label" in c]),
                         len([c for c in before if "--label" in c]))

    def test_partial_desktops_are_usable_and_can_be_completed(self):
        self.native_spaces([2,1])
        self.run_spaces()
        self.assertEqual([s["label"] for s in self.state["spaces"]], ["ws1","ws3","ws2"])
        # Inserting a left desktop changes the native index of the right ones.
        self.state["spaces"][2]["index"] = 4
        for index, display in [(3,1),(5,2),(6,2)]:
            self.state["spaces"].append(dict(index=index,display=display,label="",
                                           **{"is-native-fullscreen":False}))
        self.save()
        self.run_spaces()
        ordered = sorted(self.state["spaces"], key=lambda s:s["index"])
        self.assertEqual([s["label"] for s in ordered], ["ws1","ws3","ws5","ws2","ws4","ws6"])

    def test_custom_labels_are_preserved(self):
        self.native_spaces([3,3])
        self.state["spaces"][-1]["label"] = "personal"
        self.save()
        self.run_spaces()
        self.assertEqual(self.state["spaces"][-1]["label"], "personal")

    def test_open_laptop_adds_789_and_undocking_relabels_without_moving_windows(self):
        self.native_spaces([3,3,3])
        self.state["spaces"][0]["windows"] = [123]
        self.save()
        self.run_spaces(plan=[dict(index=1,workspaces=[1,3,5]),
                              dict(index=2,workspaces=[2,4,6]),
                              dict(index=3,workspaces=[7,8,9])])
        self.assertEqual([s["label"] for s in self.state["spaces"]],
                         ["ws1","ws3","ws5","ws2","ws4","ws6","ws7","ws8","ws9"])
        # Simulate macOS gathering native Spaces onto the remaining display.
        self.state["displays"] = self.state["displays"][:1]
        for space in self.state["spaces"]: space["display"] = 1
        self.save()
        self.run_spaces()
        self.assertEqual([s["label"] for s in self.state["spaces"]],
                         ["ws1","ws2","ws3","ws4","ws5","ws6","","",""])
        self.assertEqual(self.state["spaces"][0]["windows"], [123])


if __name__ == "__main__":
    unittest.main(verbosity=2)
