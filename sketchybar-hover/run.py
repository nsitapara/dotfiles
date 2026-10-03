#!/usr/bin/env python3
"""Build and run the hover helper from either SketchyBar profile."""
import os
from pathlib import Path
import signal
import shutil
import platform
import subprocess
import sys
import tempfile

# SketchyBar's child processes can inherit SIGCHLD=SIG_IGN on newer macOS.
# Restore waitpid behavior before compiling or querying the daemon PID.
signal.signal(signal.SIGCHLD, signal.SIG_DFL)
# SbarLua puts a 60-second alarm on exec children. This is a persistent provider.
signal.alarm(0)
os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '')
root = Path(__file__).resolve().parent
cache = Path.home() / '.cache/dotfiles/sketchybar-hover'
cache.mkdir(parents=True, exist_ok=True)


def stop():
    subprocess.run(['pkill', '-u', str(os.getuid()), '-x', 'sbar-hover'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if sys.argv[1:] == ['stop']:
    stop()
    sys.exit(0)

binary = cache / 'sbar-hover'
sources = [root / 'HoverState.swift', root / 'main.swift']
if not binary.exists() or any(p.stat().st_mtime > binary.stat().st_mtime for p in sources):
    with tempfile.TemporaryDirectory(dir=cache, prefix='build.') as build:
        output = Path(build) / 'sbar-hover'
        # A launched bar can inherit stale SDK/deployment settings after an OS upgrade.
        # Resolve compiler and SDK together, and use a supported deployment target.
        build_env = os.environ.copy()
        for key in ('SDKROOT', 'MACOSX_DEPLOYMENT_TARGET'):
            build_env.pop(key, None)
        sdk = subprocess.check_output(
            ['/usr/bin/xcrun', '--sdk', 'macosx', '--show-sdk-path'],
            env=build_env, text=True,
        ).strip()
        subprocess.run([
            '/usr/bin/xcrun', '--sdk', 'macosx', 'swiftc', '-sdk', sdk,
            '-target', platform.machine() + '-apple-macosx13.0', '-O',
            *map(str, sources), '-o', str(output),
        ], env=build_env, check=True, timeout=60)
        output.replace(binary)

# The daemon is an ancestor when this launcher is run from its Lua config.
pid = subprocess.check_output(['pgrep', '-a', '-u', str(os.getuid()), '-x', 'sketchybar'],
                              text=True).splitlines()[0]
bar = shutil.which('sketchybar')
if not bar:
    raise SystemExit('SketchyBar executable not found')
stop()
os.execv(binary, [str(binary), bar, pid, str(cache / 'instance.lock')])
