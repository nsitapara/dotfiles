import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wm_float', ROOT / 'wm-float.py')
floating = importlib.util.module_from_spec(spec)
spec.loader.exec_module(floating)


class FloatMemoryTests(unittest.TestCase):
    area = dict(x=10, y=50, w=2540, h=1382)

    def test_saved_frame_is_restored_exactly(self):
        frame = dict(x=150, y=190, w=1000, h=800)
        self.assertEqual(floating.restore_frame(dict(frame=frame, area=self.area), self.area), frame)

    def test_smaller_monitor_keeps_window_reachable(self):
        saved = dict(frame=dict(x=1800, y=500, w=750, h=850), area=self.area)
        area = dict(x=-1440, y=30, w=1440, h=770)
        result = floating.restore_frame(saved, area)
        self.assertGreaterEqual(result['x'], area['x'])
        self.assertGreaterEqual(result['y'], area['y'])
        self.assertLessEqual(result['x'] + result['w'], area['x'] + area['w'])
        self.assertLessEqual(result['y'] + result['h'], area['y'] + area['h'])
        self.assertEqual(result['h'], 770)

    def test_invalid_cache_uses_centered_default(self):
        for saved in [None, {}, dict(frame={'w': -1}, area=self.area)]:
            with self.subTest(saved=saved):
                self.assertEqual(floating.restore_frame(saved, self.area),
                                 dict(x=264, y=188, w=2032, h=1106))

    def test_float_tile_float_uses_saved_geometry(self):
        window = dict(id=1, pid=42, display=1, space=1, frame=dict(x=150, y=190, w=1000, h=800),
                      **{'is-floating': True})
        calls = []
        def run(*args):
            calls.append(args)
            if args[2:4] == ('query', '--windows'): data = window
            elif args[2:4] == ('query', '--displays'): data = dict(frame=dict(x=0,y=0,w=2560,h=1440))
            elif args[2] == 'config': data = {'top_padding':50,'bottom_padding':8,'left_padding':10,'right_padding':10}[args[-1]]
            else: data = {}
            return subprocess.CompletedProcess(args, 0, json.dumps(data), '')
        with tempfile.TemporaryDirectory() as directory, patch.object(floating, 'CACHE', Path(directory)/'frames.json'):
            floating.toggle(run)
            saved = floating.load_cache()['42:1']['frame']
            window['is-floating'] = False
            window['frame'] = dict(x=0,y=0,w=1280,h=1440)
            calls.clear()
            floating.toggle(run)
        self.assertEqual(saved, dict(x=150,y=190,w=1000,h=800))
        self.assertEqual(calls[-1],
            ('yabai','-m','window',1,'--toggle','float','--move','abs:150:190',
             '--resize','abs:1000:800','--move','abs:150:190'))

    def test_float_uses_applied_laptop_and_custom_padding(self):
        for top in [16, 50, 72]:
            calls = []
            def run(*args):
                calls.append(args)
                if args[2:4] == ('query', '--windows'):
                    data = dict(id=1, pid=42, space=3, display=2, **{'is-floating':False})
                elif args[2:4] == ('query', '--displays'):
                    data = dict(frame=dict(x=-1440,y=0,w=1440,h=900))
                elif args[2] == 'config':
                    self.assertEqual(args[3:5], ('--space', 3))
                    data = {'top_padding':top,'bottom_padding':8,'left_padding':20,'right_padding':30}[args[-1]]
                else: data = {}
                return subprocess.CompletedProcess(args, 0, json.dumps(data), '')
            with patch.object(floating, 'load_cache', return_value={}):
                floating.toggle(run)
            expected = floating.restore_frame(None, dict(x=-1420,y=top,w=1390,h=892-top))
            self.assertIn(f"abs:{expected['x']}:{expected['y']}", calls[-1])
            self.assertIn(f"abs:{expected['w']}:{expected['h']}", calls[-1])

    def test_cache_separates_windows_and_bounds_growth(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(floating, 'CACHE', Path(directory)/'frames.json'):
            cache = {str(i): dict(frame=self.area, area=self.area, at=i) for i in range(205)}
            floating.save_cache(cache, '42:1', dict(x=150,y=190,w=1000,h=800), self.area)
            loaded = floating.load_cache()
            self.assertEqual(len(loaded), 200)
            self.assertIn('42:1', loaded)
            self.assertNotIn('0', loaded)
            self.assertNotIn('99:1', loaded)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for JXA geometry parity')
    def test_aerospace_and_yabai_restore_geometry_match(self):
        saved = dict(frame=dict(x=150,y=190,w=1000,h=800),area=self.area)
        cases = [(saved,self.area), (saved,dict(x=-1440,y=30,w=1440,h=770)), (None,self.area)]
        for value,area in cases:
            script = 'const f=require(process.argv[1]); console.log(JSON.stringify(f.restoreFrame(JSON.parse(process.argv[2]),JSON.parse(process.argv[3]),0.8)))'
            result = subprocess.check_output(['node','-e',script,str(ROOT/'aerospace-float-toggle.js'),json.dumps(value),json.dumps(area)],text=True)
            self.assertEqual(json.loads(result), floating.restore_frame(value,area))


if __name__ == '__main__': unittest.main()
