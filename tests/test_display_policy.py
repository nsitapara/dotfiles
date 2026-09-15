"""Shared monitor policy and native-Space profile checks, without live changes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "yabai/.config/yabai/scripts"
PREFS = json.loads((SCRIPTS.parent / "display-preferences.json").read_text())


def screen(index, name, builtin=False, x=0):
    return dict(id=100+index, index=index, name=name, builtin=builtin,
                uuid=f"display-{index}", frame=dict(x=x, y=0, w=2560, h=1440))


class PolicyTests(unittest.TestCase):
    def plan(self, screens, prefs=None, success=True):
        result = subprocess.run(["jq", "-e", "--argjson", "prefs", json.dumps(prefs or PREFS),
                                 "-f", str(SCRIPTS / "display-layout.jq")],
                                input=json.dumps(screens), text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else None

    def test_all_supported_connections(self):
        laptop = screen(1, "Built-in Retina Display", True)
        lg = screen(2, "LG HDR QHD", x=2560)
        pa = screen(3, "PA278QV", x=-2560)
        cases = [([laptop], {101:[1,2,3,4,5,6]}),
                 ([lg], {102:[1,2,3,4,5,6]}),
                 ([laptop,lg], {101:[1,3,5],102:[2,4,6]}),
                 ([pa,laptop], {101:[1,3,5],103:[2,4,6]}),
                 ([pa,lg], {102:[1,3,5],103:[2,4,6]}),
                 ([pa,laptop,lg], {101:[7,8,9],102:[1,3,5],103:[2,4,6]})]
        for screens, expected in cases:
            with self.subTest(expected=expected):
                plan = self.plan(screens)
                self.assertEqual({s['id']:s['workspaces'] for s in plan}, expected)
                for entry in plan:
                    self.assertEqual(entry['top_padding'], 16 if entry['builtin'] else 50)

    def test_replacing_monitors_requires_only_preference_change(self):
        left, right = screen(1, 'New Left'), screen(2, 'New Right', x=2560)
        prefs = dict(PREFS, odd_monitor='New Right', even_monitor='New Left')
        plan = self.plan([left,right], prefs)
        self.assertEqual(plan[0]['workspaces'], [2,4,6])
        self.assertEqual(plan[1]['workspaces'], [1,3,5])

    def test_known_even_monitor_keeps_role_when_odd_monitor_replaced(self):
        plan = self.plan([screen(1,'PA278QV'),screen(2,'Replacement',x=2560)])
        self.assertEqual(plan[0]['workspaces'], [2,4,6])

    def test_focus_and_space_changes_do_not_change_plan(self):
        screens = [screen(1,'LG HDR QHD'),screen(2,'PA278QV',x=2560)]
        before = self.plan(screens)
        screens[0].update({'has-focus':True, 'spaces':[1,3,5]})
        screens[1].update({'has-focus':False, 'spaces':[2,4,6]})
        self.assertEqual(self.plan(screens), before)

    def test_empty_and_unsupported_topology_rejected(self):
        self.plan([], success=False)
        self.plan([screen(i,str(i)) for i in range(3)], success=False)


MOCK = r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ['PROFILE_TEST_ROOT'])
file = root/'state.json'
state = json.loads(file.read_text())
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with (root/'calls.jsonl').open('a') as log:
    log.write(json.dumps([name]+args)+'\n')
def save(): file.write_text(json.dumps(state))
if name == 'launchctl': sys.exit(0)
elif name == 'pgrep': print(42)
elif name == 'sleep': pass
elif name == 'readlink': print(str(root/state['package']/'.config/sketchybar/sketchybarrc'))
elif name == 'display-layout.sh': print(json.dumps(state['plan']))
elif name == 'ensure-spaces.sh':
    if state.get('ensure_failure'): sys.exit(1)
    if state.get('change_during_setup'):
        state['plan'][0]['frame']['x'] += 1
        save()
elif name == 'spaces.sh': pass
elif name == 'yabai':
    if args == ['-m','query','--spaces']:
        print(json.dumps([{'index':i+1,'display':s['index'],'is-native-fullscreen':False}
                          for i,s in enumerate(state['plan'])]))
elif name == 'stow':
    if '-D' not in args:
        state['package'] = args[-1]
        save()
elif name == 'sketchybar':
    if args[0] == '--reload':
        if state.get('reload_failure'): sys.exit(1)
        state['loaded'] = 'docked' if state['package'].endswith('-docked') else 'non-docked'
        save()
    else: print(json.dumps({'label':{'value':state['loaded']}},indent=2))
else: raise AssertionError((name,args))
'''


@unittest.skipUnless(sys.platform == 'darwin', 'uses macOS lockf')
class NativeProfileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='native-profile-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.here = self.root/'yabai/.config/yabai/scripts'
        self.here.mkdir(parents=True)
        self.bin = self.root/'bin'
        self.bin.mkdir()
        for directory, names in [(self.bin,['launchctl','pgrep','sleep','readlink','yabai','stow','sketchybar']),
                                 (self.here,['display-layout.sh','ensure-spaces.sh','spaces.sh'])]:
            for name in names:
                file = directory/name
                file.write_text(f'#!{sys.executable}\n'+MOCK)
                file.chmod(0o755)
        self.script = self.here/'display-profile.sh'
        shutil.copy2(SCRIPTS/'display-profile.sh', self.script)
        self.statefile = self.root/'state.json'
        self.signature = self.root/'home/.local/state/dotfiles-wm/display-profile.signature'
        self.env = dict(os.environ, HOME=str(self.root/'home'), TMPDIR=str(self.root),
                        PROFILE_TEST_ROOT=str(self.root),
                        PATH=f'{self.bin}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin')
        self.state = dict(package='sketchybar-docked',loaded='docked',
                          plan=[dict(screen(1,'Built-in',True),workspaces=[1,2,3,4,5,6],top_padding=16)])

    def run_profile(self, success=True):
        self.statefile.write_text(json.dumps(self.state))
        result = subprocess.run(['/bin/bash', str(self.script)],env=self.env,
                                capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode == 0,success,result.stdout+result.stderr)
        self.state = json.loads(self.statefile.read_text())
        return result

    def calls(self, name):
        return [c for line in (self.root/'calls.jsonl').read_text().splitlines()
                if (c:=json.loads(line))[0] == name]

    def test_laptop_profile_and_repeated_noop(self):
        self.run_profile()
        self.assertEqual(self.state['package'],'sketchybar')
        self.assertIn(['yabai','-m','config','--space','1','top_padding','16'],self.calls('yabai'))
        before = self.calls('stow'),self.calls('ensure-spaces.sh'),self.signature.stat().st_mtime_ns
        self.run_profile()
        self.assertEqual(before,(self.calls('stow'),self.calls('ensure-spaces.sh'),self.signature.stat().st_mtime_ns))
        self.assertFalse(any('aerospace' in arg for call in self.calls('stow') for arg in call))

    def test_three_screens_apply_both_padding_values_and_nine_slots(self):
        self.state['plan'][0]['workspaces'] = [7,8,9]
        self.state['plan'] += [dict(screen(2,'LG HDR QHD'),workspaces=[1,3,5],top_padding=50),
                               dict(screen(3,'PA278QV'),workspaces=[2,4,6],top_padding=50)]
        self.run_profile()
        self.assertEqual(self.state['package'],'sketchybar-docked')
        self.assertEqual(self.calls('stow'),[])
        applied = json.loads((self.signature.parent/'display-layout.json').read_text())
        self.assertEqual(sum(len(s['workspaces']) for s in applied),9)
        self.assertIn(['yabai','-m','config','--space','3','top_padding','50'],self.calls('yabai'))

    def test_creation_failure_still_applies_profile_without_repeated_setup(self):
        self.state['ensure_failure'] = True
        self.run_profile()
        self.assertEqual(self.state['package'], 'sketchybar')
        self.assertEqual(self.state['loaded'], 'non-docked')
        self.assertEqual(len(self.calls('spaces.sh')), 1)
        self.assertIn(['yabai','-m','config','--space','1','top_padding','16'], self.calls('yabai'))
        self.assertTrue(self.signature.exists())
        self.run_profile()
        self.assertEqual(len(self.calls('ensure-spaces.sh')), 1)
        self.assertEqual(sum(c[1] == '--reload' for c in self.calls('sketchybar')), 1)

    def test_topology_change_does_not_cache_success(self):
        self.state['change_during_setup'] = True
        self.run_profile(success=False)
        self.assertFalse(self.signature.exists())
        self.assertEqual(self.calls('stow'), [])

    def test_reload_failure_retries(self):
        self.state['reload_failure'] = True
        self.run_profile(success=False)
        self.assertFalse(self.signature.exists())
        self.state['reload_failure'] = False
        self.run_profile()
        self.assertTrue(self.signature.exists())


if __name__ == '__main__':
    unittest.main()
