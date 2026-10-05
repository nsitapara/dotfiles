import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/restore_omarchy.py"
spec = importlib.util.spec_from_file_location("restore_omarchy", SCRIPT)
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class RestoreTests(unittest.TestCase):
    def test_links_preserve_live_settings_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved, live, backup = root / "repo/omarchy", root / "home/.config/omarchy", root / "backup"
            saved.mkdir(parents=True)
            live.mkdir(parents=True)
            (saved / "shell.json").write_text("saved")
            (live / "shell.json").write_text("fresh defaults")
            self.assertTrue(restore.link_directory(saved, live, backup))
            self.assertTrue(live.is_symlink())
            self.assertEqual((live / "shell.json").read_text(), "saved")
            self.assertEqual((backup / "omarchy/shell.json").read_text(), "fresh defaults")
            self.assertFalse(restore.link_directory(saved, live, backup))

    def test_atomic_config_updates_keep_writing_into_dotfiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved, live = root / "repo", root / "home/omarchy"
            saved.mkdir()
            restore.link_directory(saved, live, root / "backup")
            temporary_config = live / ".shell.json.tmp"
            temporary_config.write_text("updated layout")
            temporary_config.replace(live / "shell.json")
            self.assertTrue(live.is_symlink())
            self.assertEqual((saved / "shell.json").read_text(), "updated layout")

    def test_dry_run_does_not_change_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved, live, backup = root / "repo", root / "home/omarchy", root / "backup"
            saved.mkdir()
            live.mkdir(parents=True)
            (live / "shell.json").write_text("untouched")
            restore.link_directory(saved, live, backup, dry_run=True)
            self.assertFalse(live.is_symlink())
            self.assertEqual((live / "shell.json").read_text(), "untouched")
            self.assertFalse(backup.exists())

    def test_broken_symlink_is_backed_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved, live, backup = root / "repo", root / "live", root / "backup"
            saved.mkdir()
            live.symlink_to("missing")
            restore.link_directory(saved, live, backup)
            self.assertTrue((backup / "live").is_symlink())
            self.assertEqual(live.resolve(), saved)

    def test_rejects_plugin_paths_that_escape_the_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "plugins.lock.json"
            lock.write_text(json.dumps({"version": 1, "plugins": [{
                "id": "../outside", "url": "https://github.com/example/plugin.git",
                "revision": "a" * 40, "branch": "main"}]}))
            with self.assertRaises(RuntimeError):
                restore.load_lock(lock)

    def test_existing_plugin_checkout_is_not_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            plugin = home / ".config/omarchy/plugins/example.plugin"
            plugin.mkdir(parents=True)
            (plugin / "manifest.json").write_text('{"id":"example.plugin"}')
            (plugin / "local-edit.qml").write_text("keep this")
            restore.restore_plugins(home, {"plugins": [{"id": "example.plugin"}]})
            self.assertEqual((plugin / "local-edit.qml").read_text(), "keep this")


if __name__ == "__main__":
    unittest.main()
