#!/usr/bin/env python3
"""Verify the loaded bar backend after a WM handoff; repair stale callbacks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=3)


def matches(manager):
    try:
        marker=run('sketchybar','--query','wm.backend')
        if marker.returncode or json.loads(marker.stdout).get('label',{}).get('value') != manager:
            return False
        bar=run('sketchybar','--query','bar')
        if bar.returncode:
            return False
        items=json.loads(bar.stdout)['items']
        foreign=tuple(prefix for owner,prefix in [('rift','rift.'),('yabai','yabai.')] if owner != manager)
        if any(name.startswith(foreign) for name in items):
            return False
        return manager in ('aerospace','none') or manager+'.mode' in items
    except (ValueError,KeyError,subprocess.TimeoutExpired):
        return False


def ensure(manager):
    if run('pgrep','-x','sketchybar').returncode:
        return
    if matches(manager):
        return
    # A profile marker only establishes monitor layout, not which WM owns the
    # callbacks. Reload after the handoff and verify a manager-specific marker.
    result=run('sketchybar','--reload',str(Path.home()/'.config/sketchybar/sketchybarrc'))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'SketchyBar reload failed')
    for _ in range(40):
        if matches(manager):
            return
        time.sleep(.15)
    raise RuntimeError('SketchyBar did not load the '+manager+' backend; retry ./wm.sh use '+manager)


if __name__ == '__main__':
    os.environ['PATH'] += ':/opt/homebrew/bin:/usr/local/bin'
    if len(sys.argv) != 2 or sys.argv[1] not in ('yabai','rift','aerospace','none'):
        sys.exit('Usage: wm-bar.py yabai|rift|aerospace|none')
    try:
        ensure(sys.argv[1])
    except (RuntimeError,subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
