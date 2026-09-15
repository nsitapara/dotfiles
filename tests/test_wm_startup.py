"""Login selection tests; launchctl and the live window manager are mocked."""

import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("wm_startup", Path(__file__).resolve().parents[1] / "wm-startup.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="wm login test ")
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.root = self.home / "dotfiles checkout"
        self.agent = self.home / "Library/LaunchAgents/local.dotfiles.desktop.plist"
        self.calls = []
        self.jobs = set()
        self.fail_switch = False
        self.fail_bootstrap = False
        for target, value in (("HOME", self.home), ("ROOT", self.root)):
            mock = patch.object(startup, target, value)
            mock.start()
            self.addCleanup(mock.stop)
        env = patch.dict(os.environ, {"DOTFILES_WM_STATE_DIR": str(self.home / "state")})
        env.start()
        self.addCleanup(env.stop)
        commands = patch.object(startup.subprocess, "run", side_effect=self.command)
        commands.start()
        self.addCleanup(commands.stop)

    def command(self, args, **kwargs):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["launchctl", "print"]:
            return subprocess.CompletedProcess(args, 0 if args[2].rsplit("/", 1)[-1] in self.jobs else 1)
        if args[0] == "/bin/bash" and self.fail_switch:
            raise subprocess.CalledProcessError(1, args)
        if args[:2] == ["launchctl", "bootstrap"]:
            if self.fail_bootstrap:
                raise subprocess.CalledProcessError(1, args)
            self.jobs.add(plistlib.loads(Path(args[-1]).read_bytes())["Label"])
        elif args[:2] == ["launchctl", "bootout"]:
            self.jobs.remove(args[2].rsplit("/", 1)[-1])
        return subprocess.CompletedProcess(args, 0)

    def test_login_runs_existing_switcher_without_restart_loop(self):
        startup.configure("yabai")
        config = plistlib.loads(self.agent.read_bytes())
        self.assertEqual(config["ProgramArguments"], [str(self.root / "switch-display-mode.sh"), "--service", "yabai"])
        self.assertTrue(config["RunAtLoad"])
        self.assertEqual(config["LimitLoadToSessionType"], "Aqua")
        self.assertNotIn("KeepAlive", config)
        self.assertNotIn("StartInterval", config)
        self.assertEqual(config["EnvironmentVariables"]["HOME"], str(self.home))
        self.assertEqual(self.calls[1], ["/bin/bash", str(self.root / "wm.sh"), "yabai"])
        self.assertEqual(self.jobs, {"local.dotfiles.desktop"})

    def test_failed_switch_preserves_saved_default(self):
        startup.configure("yabai")
        before = self.agent.read_bytes()
        self.calls.clear()
        self.fail_switch = True
        with self.assertRaises(subprocess.CalledProcessError):
            startup.configure("aerospace")
        self.assertEqual(self.agent.read_bytes(), before)
        self.assertFalse(any(c[1] in ("bootout", "bootstrap") for c in self.calls))

    def test_repeated_choice_does_not_reload_login_agent(self):
        startup.configure("yabai")
        self.calls.clear()
        startup.configure("yabai")
        self.assertEqual(len([c for c in self.calls if c[0] == "/bin/bash"]), 1)
        self.assertFalse(any(c[1] in ("bootout", "bootstrap") for c in self.calls))
        self.assertTrue(any(c[:2] == ["launchctl", "kickstart"] and "-k" not in c for c in self.calls))

    def test_aerospace_becomes_saved_choice(self):
        startup.configure("yabai")
        self.calls.clear()
        startup.configure("aerospace")
        self.assertEqual(plistlib.loads(self.agent.read_bytes())["ProgramArguments"][-1], "aerospace")
        self.assertEqual([c[1] for c in self.calls if c[0] == "launchctl" and c[1] != "print"],
                         ["bootout", "enable", "bootstrap"])

    def add_legacy_jobs(self):
        self.agent.parent.mkdir(parents=True, exist_ok=True)
        for label, args in [
            ("local.dotfiles.wm-login", ["switch-display-mode.sh", "--login", "aerospace"]),
            ("com.user.display-mode-switcher", ["switch-display-mode.sh"]),
        ]:
            (self.agent.parent / (label + ".plist")).write_bytes(plistlib.dumps({
                "Label": label, "ProgramArguments": args,
            }))
            self.jobs.add(label)

    def test_install_migrates_both_jobs_and_keeps_saved_choice(self):
        self.add_legacy_jobs()
        startup.configure("install")
        self.assertEqual(self.jobs, {"local.dotfiles.desktop"})
        self.assertEqual(list(self.agent.parent.glob("*.plist")), [self.agent])
        self.assertEqual(plistlib.loads(self.agent.read_bytes())["ProgramArguments"][-1], "aerospace")
        self.assertEqual(len(list((self.home / "state/disabled-launch-agents").glob("*/*.plist"))), 2)
        actions = [c[1] for c in self.calls if c[0] == "launchctl"]
        self.assertLess(actions.index("bootstrap"), actions.index("bootout"))
        startup.configure("install")
        self.assertEqual(self.jobs, {"local.dotfiles.desktop"})

    def test_failed_registration_keeps_legacy_jobs(self):
        self.add_legacy_jobs()
        before = set(self.jobs)
        self.fail_bootstrap = True
        with self.assertRaises(subprocess.CalledProcessError):
            startup.configure("install")
        self.assertEqual(self.jobs, before)
        self.assertTrue((self.agent.parent / "com.user.display-mode-switcher.plist").exists())
        self.assertTrue((self.agent.parent / "local.dotfiles.wm-login.plist").exists())

    def test_removal_keeps_current_window_manager_running(self):
        startup.configure("yabai")
        self.add_legacy_jobs()
        self.calls.clear()
        startup.configure("off")
        self.assertFalse(self.agent.exists())
        self.assertEqual(self.jobs, set())
        self.assertEqual(list(self.agent.parent.glob("*.plist")), [])
        self.assertFalse(any(c[0] == "/bin/bash" for c in self.calls))
        startup.configure("off")


if __name__ == "__main__":
    unittest.main()
