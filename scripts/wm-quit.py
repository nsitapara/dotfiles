#!/usr/bin/env python3
"""Stop window managers and their shortcut jobs, retaining the login preference."""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def run(*args,timeout=5):
    try:
        return subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args,124,'','Command timed out')


def running(name):
    return run('pgrep','-u',str(os.getuid()),'-x',name).returncode == 0


def quit_managers():
    active=[m for m in ('yabai','rift','AeroSpace') if running(m)]
    if len(active)==1:
        result=run(sys.executable,ROOT/'scripts/wm-session.py','capture',active[0].lower(),timeout=10)
        if result.returncode:
            print('Window assignment capture was unavailable; continuing emergency quit.',file=sys.stderr)
    # Reveal virtual-workspace windows before deactivation whenever IPC works.
    if 'rift' in active:
        result=run(sys.executable,ROOT/'wm_rift.py','release',timeout=20)
        if result.returncode:
            print('Rift did not release every hidden window. Restart a manager to restore captured assignments.',file=sys.stderr)
    if 'AeroSpace' in active:
        run('aerospace','enable','off')
    labels=[f'local.dotfiles.rift.{e}' for e in ('workspace_changed','windows_changed','focused_window_changed')]
    for app in ('skhd','yabai','rift','aerospace'):
        labels.extend(f'{prefix}.{app}' for prefix in ('local.dotfiles','com.asmvik','com.koekeishiya','homebrew.mxcl','com.acsandmann'))
    labels.append('bobko.aerospace')
    for label in labels:
        if run('launchctl','list',label).returncode == 0:
            run('launchctl','remove',label)
    if running('AeroSpace'):
        run('osascript','-e','tell application "AeroSpace" to quit')
    # Also stop manually launched instances, including conflicting managers.
    for app in ('skhd','yabai','rift','AeroSpace'):
        if running(app):run('pkill','-TERM','-u',str(os.getuid()),'-x',app)
    for _ in range(30):
        remaining=[app for app in ('skhd','yabai','rift','AeroSpace') if running(app)]
        if not remaining:break
        time.sleep(.1)
    else:
        raise RuntimeError('Still running: '+', '.join(remaining)+'. Quit did not complete.')
    state=Path(os.environ.get('DOTFILES_WM_STATE_DIR',Path.home()/'.local/state/dotfiles-wm'))
    state.mkdir(parents=True,exist_ok=True)
    (state/'active-manager').write_text('none\n')
    result=run(sys.executable,ROOT/'scripts/wm-bar.py','none',timeout=15)
    if result.returncode:raise RuntimeError(result.stderr.strip() or 'Stopped managers, but the bar did not refresh')
    print('Window managers stopped. Apps remain open; the saved login manager is unchanged.')


if __name__=='__main__':
    try:quit_managers()
    except RuntimeError as error:sys.exit(str(error))
