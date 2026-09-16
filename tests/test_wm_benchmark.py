"""Harness regression tests. No managers, windows or live resources are changed."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

bench=load('benchmark-window-managers')
report=load('render-wm-benchmark')
session=load('wm-session')


class BenchmarkTests(unittest.TestCase):
    def test_six_windows_on_one_workspace_cannot_start_measurement(self):
        state={'windows':[{'pid':pid,'workspace':5} for pid in (10,20) for _ in range(3)]}
        with self.assertRaisesRegex(RuntimeError,'Invalid fixture placement'):
            bench.validate_fixture(state,{10:5,20:6})
        for window in state['windows']:
            if window['pid']==20:window['workspace']=6
        bench.validate_fixture(state,{10:5,20:6})

    def test_empty_aerospace_focus_keeps_windows_in_snapshot(self):
        def query(*args):
            if args[1]=='list-windows':return [{'window-id':1,'app-pid':10,'workspace':'5','window-layout':'h_tiles','monitor-id':1}]
            if args[1]=='list-monitors':return [{'monitor-id':1,'monitor-appkit-nsscreen-screens-id':3}]
            return [{'workspace':'5'}]
        error=subprocess.CompletedProcess([],1,'','No window is focused')
        with patch.object(bench,'query',side_effect=query),patch.object(bench.subprocess,'run',return_value=error), \
             patch.object(bench.direction,'desktop_geometry',return_value={'windows':[{'id':1,'frame':{'x':0,'y':0,'w':100,'h':100}}],'displays':[]}):
            data=bench.Backend('aerospace').snapshot()
        self.assertEqual(len(data['windows']),1)
        self.assertFalse(data['windows'][0]['focused'])

    def test_empty_focus_handoff_keeps_workspace_assignment(self):
        error=subprocess.CompletedProcess([],1,'','No window is focused')
        with patch.object(session,'run',return_value=error),patch.object(session,'aerospace_windows',return_value=[
            {'window-id':1,'app-pid':10,'workspace':'2','window-layout':'h_tiles'}]),patch.object(session.rift,'write_state') as save:
            session.capture('aerospace')
        self.assertEqual(save.call_args.args[1]['windows'][0]['workspace'],2)

    def test_nonempty_focus_error_is_not_suppressed(self):
        with patch.object(session,'run',return_value=subprocess.CompletedProcess([],1,'','IPC disconnected')):
            with self.assertRaisesRegex(RuntimeError,'IPC disconnected'):session.capture('aerospace')

    def test_wait_rejects_transient_success(self):
        backend=bench.Backend('rift')
        with patch.object(backend,'snapshot',side_effect=[{'ok':True},{'ok':False},{'ok':True},{'ok':True}]) as snapshot,patch.object(bench.time,'sleep'):
            backend.wait(lambda state:state['ok'])
        self.assertEqual(snapshot.call_count,4)

    def test_report_escapes_embedded_script_end_and_keeps_raw_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json';output=Path(folder)/'report.html'
            value={'runs':[],'note':'</script><script>alert(1)</script>'}
            path.write_text(json.dumps(value));before=path.read_bytes()
            with patch('sys.argv',['render',str(path),'--output',str(output)]):report.main()
            html=output.read_text()
            payload=html.split('type="application/json">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(payload),value)
            self.assertNotIn('</script>',payload)
            self.assertEqual(path.read_bytes(),before)

    def test_even_sample_median_and_failure_count(self):
        cases=[{'name':'expand_into_side','passed':True,'command_ms':n} for n in (10,30)]
        cases.append({'name':'expand_into_side','passed':False,'command_ms':1})
        html=report.performance_summary({'runs':[{'manager':'rift','cases':cases}]})
        self.assertIn('20.0 ms',html)
        self.assertIn('2/3 passed',html)
