# Password-free startup and wake on Omarchy

Run from a terminal as your desktop user, without putting `sudo` in front:

```bash
./scripts/setup-omarchy-passwordless --check  # Read-only compatibility check
./scripts/setup-omarchy-passwordless          # Configure
./scripts/revert-omarchy-passwordless         # Restore
```

The scripts request sudo and drive passwords locally. Passwords and recovered
unlock keys are never written to the repository, command arguments, or logs.
They never reboot automatically.

## What changes

Setup enrolls a Clevis TPM2 key bound to PCR 7, preserves existing LUKS keyslots,
and tests TPM key retrieval against the encrypted drive. A local mkinitcpio
override adds `clevis` before the existing `encrypt` hook, retaining the password
fallback. It rebuilds the Limine UKIs and checks their integrity hashes and
required unlock components. Packaged Omarchy source files are not edited.

The desktop stays awake instead of automatically starting the screensaver or
locking. The user `omarchy-sleep-lock.service` is masked to prevent locking before
sleep. Manual locking remains available. Existing SDDM auto-login is preserved.

This permits physical access to the desktop without a password, as intended.
Firmware/Secure Boot changes can change PCR 7 and require the drive password.
PCR 7 binding alone is not a complete verified-boot security policy.

## Supported machines

This is reusable across **compatible Omarchy machines**, not arbitrary Linux
installations. It detects the running system's encrypted drive; no machine UUID,
username, password, or keyslot is hard-coded.

It requires:

- TPM 2 exposed as `/dev/tpmrm0` and LUKS2 directly containing the root filesystem.
- Omarchy's udev/mkinitcpio `encrypt` layout and `cryptdevice=` boot parameter.
- Limine UKIs under `/boot/EFI/Linux` with integrity hashes in `/boot/limine.conf`.
- SDDM auto-login already configured for the invoking desktop user.
- The current Omarchy shell's idle toggle and `omarchy-sleep-lock.service`.
- Python 3.11 or later and enough space to back up `/boot`.

Unsupported layouts stop before enrollment. Existing unmanaged Clevis enrollment
or a conflicting override requires manual review. Setup installs Clevis tools
from the configured Arch repositories and `mkinitcpio-clevis-hook` from the AUR
using Omarchy's package commands. This requires network access when missing.

## Rerunning and reverting

Repeated setup verifies the existing configuration without adding another keyslot
or replacing original backups. Repeated revert does nothing after restoration.
Setup can be run again after revert. System operations are serialized with a lock.
If a managed token or override was edited externally, the scripts stop for review.

Revert verifies an original drive password **before** removing TPM access. It
rebuilds the current boot image without the local TPM hook, then removes only the
exact Clevis token/keyslot created by setup. Other keyslots are retained. It
restores the saved idle preference and sleep-lock service state. Installed
packages and backups are retained.

State and backups are private to root under `/var/lib/omarchy-passwordless/`.
The session baseline lives in
`~/.local/state/omarchy/passwordless-original.json`. Keep these files: revert
uses them to identify what belongs to this setup. Do not copy them between
machines or commit them. LUKS header backups contain sensitive encryption metadata.

A failed boot rebuild restores the pre-operation boot files and local override.
An interrupted enrollment is recorded for recovery via revert. The scripts never
restore an old LUKS header automatically. If a failure is reported, resolve it
before rebooting. A real reboot is still required to validate firmware-to-desktop
behavior; static checks cannot guarantee every hardware configuration will boot.

## References and checks

- [Omarchy community Clevis guide](https://github.com/omacom/omarchy/discussions/1283)
- [Official idle toggle documentation](https://omarchy.org/manual/toggles-idle-screensaver/)

The boot rebuild uses `limine-mkinitcpio` for the current UKI layout, adapting the
older community guide's `mkinitcpio -P` instructions.

Run the regression tests without root or touching any real disk:

```bash
python3 -m unittest discover -s tests -p 'test_omarchy_passwordless.py' -v
```
