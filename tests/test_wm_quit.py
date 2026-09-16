"""Emergency quit stops managers and shortcuts without closing user apps."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('wm_quit',Path(__file__).resolve().parents[1]/'scripts/wm-quit.py')
quit=importlib.util.module_from_spec(spec);spec.loader.exec_module(quit)


class QuitTests(unittest.TestCase):
    def test_conflicting_managers_are_stopped_without_changing_login_default(self):
        active={'yabai','rift','AeroSpace','skhd'};calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[:2]==('launchctl','list'):return subprocess.CompletedProcess(args,1,'','')
            if args[0]=='pkill':active.discard(args[-1])
            return subprocess.CompletedProcess(args,0,'','')
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'DOTFILES_WM_STATE_DIR':folder}), \
             patch.object(quit,'running',side_effect=lambda name:name in active),patch.object(quit,'run',side_effect=run):
            quit.quit_managers()
            self.assertEqual(Path(folder,'active-manager').read_text(),'none\n')
        self.assertFalse(active)
        self.assertEqual({c[-1] for c in calls if c[0]=='pkill'},{'yabai','rift','AeroSpace','skhd'})
        self.assertFalse(any('wm-startup.py' in str(c) for c in calls))
        self.assertFalse(any('local.dotfiles.desktop' in str(c) for c in calls))

    def test_unresponsive_rift_release_does_not_block_emergency_stop(self):
        active={'rift'};calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[-1]=='release':return subprocess.CompletedProcess(args,124,'','timeout')
            if args[:2]==('launchctl','list'):return subprocess.CompletedProcess(args,1,'','')
            if args[0]=='pkill':active.discard(args[-1])
            return subprocess.CompletedProcess(args,0,'','')
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'DOTFILES_WM_STATE_DIR':folder}), \
             patch.object(quit,'running',side_effect=lambda name:name in active),patch.object(quit,'run',side_effect=run):
            quit.quit_managers()
        self.assertFalse(active)

    def test_process_that_wont_exit_is_reported(self):
        with patch.object(quit,'running',side_effect=lambda name:name=='yabai'), \
             patch.object(quit,'run',return_value=subprocess.CompletedProcess([],0,'','')),patch.object(quit.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'Still running: yabai'):
                quit.quit_managers()
