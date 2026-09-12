"""Shared implementation for the two terminal-facing Omarchy scripts."""
import argparse
import hashlib
import configparser
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

STATE = Path('/var/lib/omarchy-passwordless')
OVERRIDE = Path('/etc/mkinitcpio.conf.d/zz-local-tpm-unlock.conf')
SERVICE = 'omarchy-sleep-lock.service'
HOOK = '''# Managed by dotfiles: TPM unlock first, existing password fallback second.
_local_tpm_hooks=()
for _local_tpm_hook in "${HOOKS[@]}"; do
  [[ $_local_tpm_hook == encrypt ]] && _local_tpm_hooks+=(clevis)
  _local_tpm_hooks+=("$_local_tpm_hook")
done
HOOKS=("${_local_tpm_hooks[@]}")
unset _local_tpm_hooks _local_tpm_hook
'''


def run(*args, capture=False, check=True):
    return subprocess.run([str(a) for a in args], check=check, text=True,
                          stdout=subprocess.PIPE if capture else None)


def output(*args):
    return run(*args, capture=True).stdout.strip()


def save(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def root_device():
    source = output('findmnt', '-n', '-o', 'SOURCE', '/').split('[')[0]
    if output('lsblk', '-dn', '-o', 'TYPE', source) != 'crypt':
        raise RuntimeError('Supported layout: root directly on LUKS (no intermediate LVM/RAID).')
    status = output('cryptsetup', 'status', source)
    match = re.search(r'^\s*device:\s*(\S+)', status, re.M)
    if not match:
        raise RuntimeError('Cannot identify the encrypted root partition.')
    device = match[1]
    uuid = output('cryptsetup', 'luksUUID', device)
    if not re.fullmatch(r'[0-9a-f-]{36}', uuid):
        raise RuntimeError('Invalid LUKS UUID.')
    return device, uuid


def metadata(device):
    return json.loads(output('cryptsetup', 'luksDump', '--dump-json-metadata', device))


def boot_entries(config):
    entries = re.findall(r'path:\s*boot\(\):(/EFI/Linux/[^\s#]+\.efi)#([0-9a-f]{128})', config)
    if not entries:
        raise RuntimeError('Expected Limine UKIs with integrity hashes under /boot/EFI/Linux.')
    return dict(entries)


def verify_boot(tpm):
    for relative, expected in boot_entries(Path('/boot/limine.conf').read_text()).items():
        image = Path('/boot') / relative.lstrip('/')
        with image.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'blake2b').hexdigest()
        if actual != expected:
            raise RuntimeError(f'Boot image integrity mismatch: {image}')
        contents = output('lsinitcpio', image).splitlines()
        if 'hooks/encrypt' not in contents:
            raise RuntimeError(f'Missing password fallback in {image}')
        if ('hooks/clevis' in contents) != tpm:
            raise RuntimeError(f'Unexpected TPM hook state in {image}')
        if tpm:
            for required in ('usr/bin/clevis-luks-unlock', 'usr/bin/tpm2_unseal',
                             'usr/bin/cryptsetup', 'usr/bin/jose'):
                if required not in contents:
                    raise RuntimeError(f'Missing {required} in {image}')
        print(f'PASS: boot image integrity and unlock hooks: {image}')


def preflight():
    for command in ('cryptsetup', 'lsblk', 'findmnt', 'findfs', 'limine-mkinitcpio', 'lsinitcpio'):
        if not shutil.which(command):
            raise RuntimeError(f'Missing required command: {command}')
    if not Path('/dev/tpmrm0').exists():
        raise RuntimeError('No TPM 2 resource-manager device found.')
    if not Path('/usr/share/omarchy').is_dir():
        raise RuntimeError('This script supports Omarchy, not other distributions.')
    device, uuid = root_device()
    spec = re.search(r'(?:^|\s)cryptdevice=([^: ]+):', Path('/proc/cmdline').read_text())
    if not spec:
        raise RuntimeError('Expected the existing udev/encrypt boot layout (cryptdevice=).')
    boot_device = output('findfs', spec[1]) if '=' in spec[1] else spec[1]
    if os.path.realpath(boot_device) != os.path.realpath(device):
        raise RuntimeError('Boot command line does not match the running encrypted root.')
    config = output('bash', '-c', 'source /etc/mkinitcpio.conf; '
                    'for f in /etc/mkinitcpio.conf.d/*.conf; do [[ ! -f $f ]] || source "$f"; done; '
                    'printf "%s\\n" "${HOOKS[@]}"').splitlines()
    if 'encrypt' not in config or 'systemd' in config or 'sd-encrypt' in config:
        raise RuntimeError('Unsupported initramfs configuration; no settings changed.')
    boot_entries(Path('/boot/limine.conf').read_text())
    login = configparser.ConfigParser(strict=False)
    login.read(['/usr/lib/sddm/sddm.conf.d/default.conf'] +
               sorted(str(p) for p in Path('/etc/sddm.conf.d').glob('*.conf')) + ['/etc/sddm.conf'])
    username = os.environ.get('SUDO_USER')
    if not username or login.get('Autologin', 'User', fallback='') != username:
        raise RuntimeError('Enable SDDM auto-login for your desktop user first; this tool preserves login configuration.')
    data = metadata(device)  # Fails safely for LUKS1.
    if not data['keyslots']:
        raise RuntimeError('No existing LUKS keyslot found.')
    print(f'Encrypted root: {device} (LUKS UUID {uuid})')
    return device, uuid, data


def test_tpm(device, slot):
    # The generated unlock secret travels only over a pipe, never argv/logs/files.
    with subprocess.Popen(['clevis', 'luks', 'pass', '-d', device, '-s', slot],
                          stdout=subprocess.PIPE) as producer:
        result = subprocess.run(['cryptsetup', 'open', '--test-passphrase',
                                 '--key-file=-', device], stdin=producer.stdout)
        producer.stdout.close()
        code = producer.wait()
    if code or result.returncode:
        raise RuntimeError('TPM retrieval/unlock test failed; boot configuration was not changed.')
    print('PASS: TPM recovered a working unlock key')


def backup_boot(label):
    dest = Path(tempfile.mkdtemp(prefix=label + '-', dir=STATE))
    size = sum(p.stat().st_size for p in Path('/boot').rglob('*') if p.is_file())
    if shutil.disk_usage(STATE).free < size + 100 * 1024**2:
        raise RuntimeError('Not enough free space for a boot backup.')
    run('cp', '-a', '/boot', dest / 'boot')
    return dest


def rebuild_with_rollback(backup, previous_override, tpm):
    try:
        run('limine-mkinitcpio')
        verify_boot(tpm)
    except BaseException:
        if previous_override is None:
            OVERRIDE.unlink(missing_ok=True)
        else:
            OVERRIDE.write_text(previous_override)
        run('cp', '-a', str(backup / 'boot') + '/.', '/boot/')
        print(f'Restored pre-operation boot files from {backup}; do not reboot until reviewed.', file=sys.stderr)
        raise


def added_slot(before, after):
    added = set(after['keyslots']) - set(before['keyslots'])
    if len(added) != 1:
        raise RuntimeError('Expected exactly one added keyslot; stopping without deleting any keys.')
    slot = added.pop()
    matches = [(k, v) for k, v in after['tokens'].items()
               if v.get('type') == 'clevis' and slot in v.get('keyslots', [])]
    if len(matches) != 1:
        raise RuntimeError('Cannot uniquely identify the newly added Clevis token.')
    return slot, matches[0][0], matches[0][1]


def system_setup():
    device, uuid, before = preflight()
    statefile = STATE / 'state.json'
    if statefile.exists():
        state = json.loads(statefile.read_text())
        if state['uuid'] != uuid:
            raise RuntimeError('Saved state belongs to a different encrypted drive.')
        if state['phase'] == 'reverted':
            statefile.replace(STATE / 'last-reverted-state.json')
            return system_setup()
        if state['phase'] == 'enabled':
            if before.get('tokens', {}).get(state['token_id']) != state['token']:
                raise RuntimeError('Managed TPM token has changed; refusing to modify enrollment.')
            if OVERRIDE.read_text() != state['override']:
                raise RuntimeError('Managed boot override was edited; review it before proceeding.')
            verify_boot(True)
            test_tpm(device, state['slot'])
            print('Already configured; original backups retained.')
            return
        raise RuntimeError('An earlier operation is incomplete. Run revert before trying setup again.')
    if OVERRIDE.exists():
        raise RuntimeError('Existing TPM override is unmanaged; review/import it before setup.')
    if any(t.get('type') == 'clevis' for t in before.get('tokens', {}).values()):
        raise RuntimeError('Existing Clevis enrollment is unmanaged; refusing to add another.')
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE.chmod(0o700)
    backup = backup_boot('setup')
    run('cryptsetup', 'luksHeaderBackup', device, '--header-backup-file', backup / 'luks-header.img')
    state = {'uuid': uuid, 'before_slots': sorted(before['keyslots']),
             'backup': str(backup), 'phase': 'prepared'}
    save(statefile, state)
    print('Enter your existing DRIVE password at the Clevis prompt.', flush=True)
    try:
        run('clevis', 'luks', 'bind', '-d', device, 'tpm2',
            '{"pcr_bank":"sha256","pcr_ids":"7"}')
    finally:
        after = metadata(device)
        if set(after['keyslots']) != set(before['keyslots']):
            slot, token_id, token = added_slot(before, after)
            state.update(slot=slot, token_id=token_id, token=token, phase='enrolled')
            save(statefile, state)
    test_tpm(device, state['slot'])
    state['override'] = HOOK
    save(statefile, state)
    OVERRIDE.write_text(HOOK)
    OVERRIDE.chmod(0o644)
    rebuild_with_rollback(backup, None, True)
    state['phase'] = 'enabled'
    save(statefile, state)
    print(f'TPM setup complete. Backup: {backup}')


def system_revert():
    statefile = STATE / 'state.json'
    if not statefile.exists():
        print('No managed system setup exists; nothing to revert.')
        return
    state = json.loads(statefile.read_text())
    if state['phase'] == 'reverted':
        print('System settings already reverted.')
        return
    device, uuid = root_device()
    if uuid != state['uuid']:
        raise RuntimeError('Saved state belongs to a different encrypted drive.')
    data = metadata(device)
    slot = state.get('slot')
    if (state['phase'] == 'password-boot' and slot not in data['keyslots']
            and state.get('token_id') not in data.get('tokens', {})):
        state['phase'] = 'reverted'
        save(statefile, state)
        return
    if OVERRIDE.exists() and OVERRIDE.read_text() != state.get('override'):
        raise RuntimeError('Managed boot override was edited; refusing to discard custom changes.')
    if slot:
        if data.get('tokens', {}).get(state['token_id']) != state['token']:
            raise RuntimeError('TPM token changed since setup; refusing to delete it.')
        candidates = set(state['before_slots']) & set(data['keyslots']) - {slot}
        if not candidates:
            raise RuntimeError('No original keyslot remains. Refusing to remove TPM access.')
        print('First verify your original DRIVE password; TPM access is retained if this fails.', flush=True)
        # Setup supports the usual Omarchy password slot. Other original slots
        # can be tried individually without ever deleting a slot on failure.
        verified = False
        for candidate in sorted(candidates):
            if run('cryptsetup', 'open', '--test-passphrase', '--key-slot', candidate,
                   device, check=False).returncode == 0:
                verified = True
                break
        if not verified:
            raise RuntimeError('Original password verification failed; nothing removed.')
    backup = backup_boot('revert')
    previous = OVERRIDE.read_text() if OVERRIDE.exists() else None
    OVERRIDE.unlink(missing_ok=True)
    rebuild_with_rollback(backup, previous, False)
    state['phase'] = 'password-boot'
    save(statefile, state)
    if slot:
        # Never use luksKillSlot or restore an old LUKS header automatically.
        run('clevis', 'luks', 'unbind', '-f', '-d', device, '-s', slot)
    state['phase'] = 'reverted'
    save(statefile, state)
    print('Password-based startup restored. Backups and installed packages retained.')


def user_state_path():
    return Path.home() / '.local/state/omarchy/passwordless-original.json'


def session_setup():
    path = user_state_path()
    if not path.exists():
        unit = run('systemctl', '--user', 'is-enabled', SERVICE, capture=True, check=False).stdout.strip()
        active = run('systemctl', '--user', 'is-active', SERVICE, capture=True, check=False).stdout.strip()
        if unit not in ('enabled', 'disabled', 'static', 'masked', 'masked-runtime'):
            raise RuntimeError(f'Unsupported sleep-lock service state: {unit}')
        save(path, {'stay_awake': (Path.home() / '.local/state/omarchy/indicators/stay-awake').exists(),
                    'service': unit, 'active': active == 'active'})
    run('omarchy', 'toggle', 'idle', 'stay-awake')
    run('systemctl', '--user', 'mask', '--now', SERVICE)


def session_revert():
    path = user_state_path()
    if not path.exists():
        print('No managed session settings remain; nothing to revert.')
        return
    state = json.loads(path.read_text())
    run('omarchy', 'toggle', 'idle', 'stay-awake' if state['stay_awake'] else 'allow-idle')
    run('systemctl', '--user', 'unmask', SERVICE)
    if state['service'] == 'masked':
        run('systemctl', '--user', 'mask', '--now', SERVICE)
    elif state['service'] == 'masked-runtime':
        run('systemctl', '--user', 'mask', '--runtime', '--now', SERVICE)
    elif state['active']:
        run('systemctl', '--user', 'start', SERVICE)
    path.replace(path.with_suffix('.reverted.json'))


def main(action):
    parser = argparse.ArgumentParser(description=f'{action.title()} TPM startup unlock and automatic-lock changes on Omarchy.')
    parser.add_argument('--check', action='store_true', help='Read-only system compatibility checks; do not install or change settings.')
    parser.add_argument('--system', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.system:
            if os.geteuid() != 0:
                raise RuntimeError('System phase requires root.')
            if args.check:
                preflight()
            else:
                with open('/run/lock/omarchy-passwordless.lock', 'w') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    if action == 'setup':
                        system_setup()
                    else:
                        system_revert()
            return
        if os.geteuid() == 0:
            raise RuntimeError('Run this script as your desktop user, not with sudo. It elevates only system work.')
        if not sys.stdin.isatty():
            raise RuntimeError('Run in a local terminal so passwords can be entered privately.')
        script = Path(sys.argv[0]).resolve()
        if args.check:
            run('sudo', sys.executable, script, '--system', '--check')
            return
        if action == 'setup':
            # Check compatibility before installing packages or modifying the session.
            run('sudo', sys.executable, script, '--system', '--check')
            run('omarchy', 'pkg', 'add', 'clevis', 'tpm2-tools', 'tpm2-tss', 'luksmeta', 'libpwquality', 'tpm2-abrmd')
            if run('pacman', '-Q', 'mkinitcpio-clevis-hook', capture=True, check=False).returncode:
                run('omarchy', 'pkg', 'aur', 'add', 'mkinitcpio-clevis-hook')
            run('sudo', sys.executable, script, '--system')
            session_setup()
        else:
            run('sudo', sys.executable, script, '--system')
            session_revert()
        print('Done. No reboot performed. Reboot when ready to test the full startup path.')
    except (RuntimeError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print(f'STOPPED: {exc}', file=sys.stderr)
        raise SystemExit(1)
