#!/usr/bin/env python3
"""Install the official Rift release archive without compiling it or starting it."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

VERSION = '0.5.9'
SHA256 = '31c2bf50d9f731e48598d497e06832d8587203824c3db5fda993401acf8b8d4b'
URL = f'https://github.com/acsandmann/rift/releases/download/v{VERSION}/rift-universal-macos-{VERSION}.tar.gz'


def main():
    # Prefer an existing package installation. Version compatibility is checked
    # before every switch, and upgrades are always an explicit install action.
    installed = shutil.which('rift')
    if installed and subprocess.run([installed, '--version'], capture_output=True, text=True).stdout.strip().endswith(VERSION):
        print(f'Rift {VERSION} already installed at {installed}')
        return
    target = Path.home() / '.local/opt/rift' / VERSION
    bindir = Path.home() / '.local/bin'
    bindir.mkdir(parents=True, exist_ok=True)
    for name in ('rift', 'rift-cli'):
        link = bindir / name
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or '.local/opt/rift/' not in str(link.resolve()):
                raise RuntimeError(f'Refusing to overwrite {link}')
    if not target.exists():
        print(f'Downloading official Rift {VERSION} release', flush=True)
        data = urllib.request.urlopen(URL, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError('Rift archive checksum does not match the official Homebrew formula')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
            staging = Path(temporary) / VERSION
            staging.mkdir()
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                for name in ('rift', 'rift-cli'):
                    candidates = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == name]
                    if len(candidates) != 1:
                        raise RuntimeError(f'Expected exactly one {name} executable')
                    destination = staging / name
                    destination.write_bytes(archive.extractfile(candidates[0]).read())
                    destination.chmod(0o755)
                    # Match the official formula's local ad-hoc signing step.
                    subprocess.run(['codesign', '--force', '-s', '-', str(destination)], check=True)
            staging.rename(target)
    for name in ('rift', 'rift-cli'):
        link = bindir / name
        temporary = bindir / ('.' + name + '.' + str(os.getpid()))
        temporary.symlink_to(target / name)
        temporary.replace(link)
    subprocess.run([str(target / 'rift'), '--version'], check=True)
    print(f'Installed to {target}. Nothing started.')


if __name__ == '__main__':
    main()
