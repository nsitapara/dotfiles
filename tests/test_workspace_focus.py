"""Restore a real window after native Space activation without stealing focus."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('focus_space', ROOT/'yabai/.config/yabai/scripts/focus-space.py')
focus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(focus)


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.space = {'id':9,'index':4,'windows':[22,21]}
        self.windows = [dict(id=id,space=4,**{'is-visible':True,'has-focus':False}) for id in [21,22]]
        self.focused = None
        self.commands = []
        self.addCleanup(patch.stopall)
        patch.object(focus.time,'sleep').start()
        patch.object(focus,'query',side_effect=self.query).start()
        patch.object(focus,'command',side_effect=self.command).start()

    def query(self,*args):
        if args[:2] == ('--spaces','--space'): return self.space
        if args == ('--windows','--window'): return self.focused
        if args == ('--windows','--space',4): return self.windows
        raise AssertionError(args)

    def command(self,*args):
        self.commands.append(args)
        if args[:2] == ('window','--focus'):
            self.focused = dict(next(w for w in self.windows if w['id'] == args[2]),**{'has-focus':True})
        return SimpleNamespace(returncode=0,stderr='')

    def test_finder_without_a_window_focuses_frontmost_destination_window(self):
        focus.restore(self.space)
        self.assertEqual(self.commands,[('window','--focus',22)])

    def test_existing_selection_is_preserved(self):
        self.focused = dict(self.windows[0],**{'has-focus':True})
        focus.restore(self.space)
        self.assertEqual(self.commands,[])

    def test_window_on_other_monitor_does_not_count_as_destination_focus(self):
        self.focused = dict(id=99,space=1,**{'has-focus':True,'is-visible':True})
        focus.restore(self.space)
        self.assertEqual(self.commands,[('window','--focus',22)])

    def test_floating_windows_can_receive_focus(self):
        self.windows[1]['is-floating'] = True
        focus.restore(self.space)
        self.assertEqual(self.commands,[('window','--focus',22)])

    def test_hidden_and_minimized_windows_are_not_activated(self):
        self.windows[0]['is-hidden'] = True
        self.windows[1]['is-minimized'] = True
        focus.restore(self.space)
        self.assertEqual(self.commands,[])

    def test_empty_workspace_remains_empty(self):
        self.windows = []
        focus.restore(self.space)
        self.assertEqual(self.commands,[])

    def test_late_event_does_not_pull_user_back_to_previous_space(self):
        old = dict(self.space)
        self.space = dict(id=99,index=6,windows=[])
        focus.restore(old)
        self.assertEqual(self.commands,[])

    def test_navigation_during_window_query_cancels_focus(self):
        original = self.query
        def query(*args):
            result = original(*args)
            if args == ('--windows','--space',4):
                self.space = dict(id=99,index=6,windows=[])
            return result
        with patch.object(focus,'query',side_effect=query): focus.restore(self.space)
        self.assertEqual(self.commands,[])

    def test_switch_uses_native_index_and_then_focuses_window(self):
        focus.switch('ws2')
        self.assertEqual(self.commands,[('space','--focus',4),('window','--focus',22)])

    def test_already_focused_space_can_still_recover_window_focus(self):
        original = self.command
        def command(*args):
            if args[:2] == ('space','--focus'):
                return SimpleNamespace(returncode=1,stderr='cannot focus an already focused space')
            return original(*args)
        with patch.object(focus,'command',side_effect=command): focus.switch('ws2')
        self.assertEqual(self.commands,[('window','--focus',22)])

    def test_native_fullscreen_is_left_to_macos(self):
        self.space['is-native-fullscreen'] = True
        focus.restore(self.space)
        self.assertEqual(self.commands,[])


if __name__ == '__main__': unittest.main()
