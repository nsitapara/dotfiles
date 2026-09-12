import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('passwordless', Path(__file__).parents[1] / 'scripts/omarchy_passwordless.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.override = self.root / 'override.conf'
        self.before = {'keyslots': {'0': {}}, 'tokens': {}}
        self.data = copy.deepcopy(self.before)
        self.calls = []
        self.password_ok = True
        for target, value in [('STATE', self.state), ('OVERRIDE', self.override),
                              ('preflight', lambda: ('/dev/test', 'test-uuid', copy.deepcopy(self.data))),
                              ('root_device', lambda: ('/dev/test', 'test-uuid')),
                              ('metadata', lambda device: copy.deepcopy(self.data)),
                              ('run', self.fake_run), ('backup_boot', lambda label: self.root),
                              ('test_tpm', lambda *args: None), ('verify_boot', lambda *args: None),
                              ('rebuild_with_rollback', lambda *args: None)]:
            p = patch.object(m, target, value)
            p.start()
            self.addCleanup(p.stop)

    def fake_run(self, *args, **kwargs):
        self.calls.append(args)
        if args[:3] == ('clevis', 'luks', 'bind'):
            self.data['keyslots']['1'] = {}
            self.data['tokens']['0'] = {'type': 'clevis', 'keyslots': ['1'], 'jwe': 'test-sealed-data'}
        if args[:3] == ('clevis', 'luks', 'unbind'):
            del self.data['keyslots']['1']
            del self.data['tokens']['0']
        code = 0 if self.password_ok or '--test-passphrase' not in args else 1
        return subprocess.CompletedProcess(args, code)

    def test_setup_revert_and_setup_again_are_idempotent(self):
        m.system_setup()
        original = (self.state / 'state.json').read_text()
        calls = len(self.calls)
        m.system_setup()
        self.assertEqual(len(self.calls), calls)
        self.assertEqual((self.state / 'state.json').read_text(), original)
        m.system_revert()
        self.assertEqual(self.data, self.before)
        calls = len(self.calls)
        m.system_revert()
        self.assertEqual(len(self.calls), calls)
        m.system_setup()
        self.assertEqual(set(self.data['keyslots']), {'0', '1'})

    def test_wrong_password_cannot_remove_tpm_or_override(self):
        m.system_setup()
        self.password_ok = False
        with self.assertRaisesRegex(RuntimeError, 'verification failed'):
            m.system_revert()
        self.assertIn('1', self.data['keyslots'])
        self.assertTrue(self.override.exists())

    def test_modified_token_is_never_removed(self):
        m.system_setup()
        self.data['tokens']['0']['jwe'] = 'somebody-elses-token'
        with self.assertRaisesRegex(RuntimeError, 'token changed'):
            m.system_revert()
        self.assertIn('1', self.data['keyslots'])

    def test_modified_override_is_not_discarded(self):
        m.system_setup()
        self.override.write_text('custom setting')
        with self.assertRaisesRegex(RuntimeError, 'override was edited'):
            m.system_revert()
        self.assertEqual(self.override.read_text(), 'custom setting')

    def test_different_drive_is_not_modified(self):
        m.system_setup()
        with patch.object(m, 'root_device', return_value=('/dev/other', 'other-uuid')):
            with self.assertRaisesRegex(RuntimeError, 'different encrypted drive'):
                m.system_revert()
        self.assertIn('1', self.data['keyslots'])

    def test_retry_after_completed_unbind_is_safe(self):
        m.system_setup()
        path = self.state / 'state.json'
        state = json.loads(path.read_text())
        state['phase'] = 'password-boot'
        m.save(path, state)
        self.data = copy.deepcopy(self.before)
        self.override.unlink()
        m.system_revert()
        self.assertEqual(json.loads(path.read_text())['phase'], 'reverted')

    def test_unmanaged_enrollment_is_not_adopted_silently(self):
        self.data['tokens']['5'] = {'type': 'clevis', 'keyslots': ['0']}
        with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
            m.system_setup()
        self.assertEqual(self.calls, [])


class BootConfiguration(unittest.TestCase):
    def test_hook_inserts_tpm_before_password_fallback(self):
        cmd = 'HOOKS=(base udev plymouth encrypt filesystems btrfs-overlayfs)\n' + m.HOOK
        cmd += '\nprintf "%s\\n" "${HOOKS[@]}"'
        result = subprocess.check_output(['bash', '-c', cmd], text=True).splitlines()
        self.assertEqual(result, ['base', 'udev', 'plymouth', 'clevis', 'encrypt', 'filesystems', 'btrfs-overlayfs'])

    def test_unsupported_boot_layout_is_rejected(self):
        with self.assertRaises(RuntimeError):
            m.boot_entries('path: /some/other/bootloader')

    def test_only_current_uki_entries_are_selected(self):
        digest = 'a' * 128
        text = f'path: boot():/EFI/Linux/omarchy_linux.efi#{digest}\npath: boot():/history/old.efi#{digest}'
        self.assertEqual(m.boot_entries(text), {'/EFI/Linux/omarchy_linux.efi': digest})


class SessionState(unittest.TestCase):
    def test_repeated_setup_keeps_original_and_revert_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            def fake_run(*args, **kwargs):
                calls.append(args)
                result = 'disabled' if 'is-enabled' in args else 'inactive'
                return subprocess.CompletedProcess(args, 0, stdout=result)
            with patch.object(Path, 'home', return_value=Path(tmp)), patch.object(m, 'run', fake_run):
                m.session_setup()
                original = m.user_state_path().read_text()
                m.session_setup()
                self.assertEqual(m.user_state_path().read_text(), original)
                m.session_revert()
                self.assertIn(('omarchy', 'toggle', 'idle', 'allow-idle'), calls)
                self.assertNotIn(('systemctl', '--user', 'start', m.SERVICE), calls)
                count = len(calls)
                m.session_revert()
                self.assertEqual(len(calls), count)


if __name__ == '__main__':
    unittest.main()
