#!/usr/bin/env python3
"""Build and run the hover helper from either SketchyBar profile."""
import os
from pathlib import Path
import signal
import shutil
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
        subprocess.run(['swiftc', '-O', *map(str, sources), '-o', str(output)], check=True)
        output.replace(binary)

# The daemon is an ancestor when this launcher is run from its Lua config.
pid = subprocess.check_output(['pgrep', '-a', '-u', str(os.getuid()), '-x', 'sketchybar'],
                              text=True).splitlines()[0]
bar = shutil.which('sketchybar')
if not bar:
    raise SystemExit('SketchyBar executable not found')
stop()
os.execv(binary, [str(binary), bar, pid, str(cache / 'instance.lock')])
