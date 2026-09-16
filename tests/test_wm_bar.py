"""Bar handoff regression tests, without changing the desktop."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('wm_bar',Path(__file__).resolve().parents[1]/'scripts/wm-bar.py')
bar=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bar)


class BarTests(unittest.TestCase):
    def result(self,value=None,code=0):
        return subprocess.CompletedProcess([],code,json.dumps(value), '')

    def test_matching_backend_rejects_stale_foreign_pills(self):
        for target,foreign in [('yabai','rift.space.native201'),('rift','yabai.space.2')]:
            with self.subTest(target=target),patch.object(bar,'run',side_effect=[
                self.result({'label':{'value':target}}),self.result({'items':[target+'.mode',foreign]})]):
                self.assertFalse(bar.matches(target))

    def test_profile_marker_cannot_stand_in_for_manager_identity(self):
        with patch.object(bar,'run',return_value=self.result({'label':{'value':'docked'}})):
            self.assertFalse(bar.matches('yabai'))

    def test_wrong_backend_reloads_and_waits_for_new_callbacks(self):
        with patch.object(bar,'run',return_value=self.result()) as run, \
             patch.object(bar,'matches',side_effect=[False,False,True]),patch.object(bar.time,'sleep'):
            bar.ensure('yabai')
        self.assertEqual([c.args[:2] for c in run.call_args_list],[('pgrep','-x'),('sketchybar','--reload')])

    def test_healthy_bar_is_not_reloaded(self):
        with patch.object(bar,'run',return_value=self.result()) as run,patch.object(bar,'matches',return_value=True):
            bar.ensure('rift')
        self.assertEqual(run.call_count,1)

    def test_reload_success_without_correct_backend_is_failure(self):
        with patch.object(bar,'run',return_value=self.result()),patch.object(bar,'matches',return_value=False),patch.object(bar.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'did not load'):
                bar.ensure('yabai')

    def test_stopped_bar_is_left_stopped(self):
        with patch.object(bar,'run',return_value=self.result(code=1)) as run:
            bar.ensure('yabai')
        self.assertEqual(run.call_count,1)
