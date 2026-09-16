#!/usr/bin/env python3
"""Controlled, reversible WM behavior and resource benchmark on this desktop.

Uses temporary AppKit windows on empty workspaces 5 and 6. Never closes existing
user windows. Keep keyboard/mouse idle during the live run. Output contains no
window titles, document contents, or unrelated process arguments.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wm_rift as rift
from scripts.wm import rift_geometry


def run(*args, timeout=90):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'Command failed').strip()[-1500:])
    return result.stdout


def query(*args):
    return json.loads(run(*args))


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


direction = load('wm-direction')


def validate_fixture(state, assignments):
    """Never measure a different window count or workspace than requested."""
    for pid,number in assignments.items():
        windows=[w for w in state['windows'] if w['pid']==pid]
        if len(windows)!=3 or any(w['workspace']!=number for w in windows):
            raise RuntimeError(f'Invalid fixture placement: expected three windows from fixture {pid} on workspace {number}')


def seconds(value):
    parts = value.split(':')
    return sum(float(part)*60**i for i,part in enumerate(reversed(parts)))


class Resources:
    """Sample cumulative CPU and RSS, retaining data for processes that exit."""
    def __init__(self, manager):
        self.manager = manager
        self.samples = []
        self.first, self.last, self.groups = {}, {}, {}
        self.stop = threading.Event()

    def sample(self):
        output = run('/bin/ps','-axo','pid=,ppid=,rss=,time=,comm=')
        rows = {}
        for line in output.splitlines():
            parts=line.strip().split(None,4)
            if len(parts)!=5: continue
            pid,parent,rss,cpu,comm=parts
            rows[int(pid)]=dict(parent=int(parent),rss=int(rss)/1024,cpu=seconds(cpu),name=Path(comm).name)
        groups={}
        for pid,row in rows.items():
            name=row['name']
            if name == {'aerospace':'AeroSpace'}.get(self.manager,self.manager): groups[pid]='manager'
            elif name == 'skhd': groups[pid]='shortcuts'
            elif name == 'rift-cli': groups[pid]='events_and_cli'
            elif name in ('sketchybar','WindowServer'): groups[pid]=name
        # Identify only our named helper scripts, never collect process arguments.
        for script in ('aerospace-poll.sh','aerospace-retile.sh','wm_rift.py'):
            found=subprocess.run(['pgrep','-f',str(ROOT/script)],capture_output=True,text=True)
            for pid in found.stdout.split():
                if pid.isdigit() and int(pid)!=os.getpid(): groups[int(pid)]='helpers'
        changed=True
        while changed:
            changed=False
            for pid,row in rows.items():
                if pid in groups: continue
                parent_group=groups.get(row['parent'])
                if parent_group and parent_group not in ('sketchybar','WindowServer'):
                    groups[pid]='helpers'; changed=True
                elif row['parent']==os.getpid() and row['name'] not in ('LayoutCheck','ps','pgrep'):
                    groups[pid]='helpers'; changed=True
        totals={}
        for pid,group in groups.items():
            row=rows.get(pid)
            if not row: continue
            if pid not in self.first:
                self.first[pid]=row['cpu'] if not self.samples else 0
            self.last[pid]=row['cpu']; self.groups[pid]=group
            data=totals.setdefault(group,dict(rss_mb=0,processes=0))
            data['rss_mb']+=row['rss'];data['processes']+=1
        for group in set(self.groups.values()):
            totals.setdefault(group,dict(rss_mb=0,processes=0))['cpu_seconds']=sum(
                max(0,self.last[p]-self.first[p]) for p in self.last if self.groups[p]==group)
        self.samples.append(dict(at=time.monotonic()-self.started,groups=totals))

    def __enter__(self):
        self.started=time.monotonic()
        self.sample()
        def loop():
            while not self.stop.wait(.2): self.sample()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
        return self

    def __exit__(self,*_):
        self.stop.set();self.thread.join();self.sample()

    def result(self):
        elapsed=self.samples[-1]['at']
        groups={}
        for group in set(self.groups.values()):
            memory=[s['groups'].get(group,{}).get('rss_mb',0) for s in self.samples]
            cpu=sum(max(0,self.last[p]-self.first[p]) for p in self.last if self.groups[p]==group)
            groups[group]=dict(cpu_percent_one_core=100*cpu/elapsed,cpu_seconds=cpu,
                               mean_rss_mb=statistics.mean(memory),peak_rss_mb=max(memory))
        return dict(duration_seconds=elapsed,groups=groups,samples=self.samples)


class Backend:
    def __init__(self,name): self.name=name

    def snapshot(self):
        if self.name=='rift':
            data=rift.snapshot(); ids={d['uuid']:d['screen_id'] for d in data['displays']}
            windows=[dict(w,display=ids[w['display']]) for w in data['windows']]
            displays=[dict(id=d['screen_id'],frame=rift.rect(d['frame'])) for d in data['displays']]
        elif self.name=='yabai':
            spaces={s['index']:s for s in query('yabai','-m','query','--spaces')}
            ds=query('yabai','-m','query','--displays'); ids={d['index']:d['id'] for d in ds}
            windows=[]
            for w in query('yabai','-m','query','--windows'):
                label=spaces.get(w['space'],{}).get('label','')
                windows.append(dict(id=w['id'],pid=w['pid'],frame=w['frame'],display=ids[w['display']],
                    workspace=int(label[2:]) if re.fullmatch(r'ws[1-9]',label) else None,
                    focused=w['has-focus'],floating=w['is-floating'],visible=w['is-visible']))
            displays=[dict(id=d['id'],frame=d['frame']) for d in ds]
        else:
            rows=query('aerospace','list-windows','--all','--json','--format',
                       '%{window-id} %{app-pid} %{workspace} %{window-layout} %{monitor-id}')
            result=subprocess.run(['aerospace','list-windows','--focused','--json'],capture_output=True,text=True,timeout=5)
            if result.returncode and 'No window is focused' not in result.stderr+result.stdout:
                raise RuntimeError(result.stderr or result.stdout)
            focused=json.loads(result.stdout) if result.returncode == 0 else []
            focused=focused[0]['window-id'] if focused else None
            ds=query('aerospace','list-monitors','--json','--format','%{monitor-id} %{monitor-appkit-nsscreen-screens-id}')
            ids={d['monitor-id']:d['monitor-appkit-nsscreen-screens-id'] for d in ds}
            geometry=direction.desktop_geometry(); frames={w['id']:w['frame'] for w in geometry['windows']}
            visible={w['workspace'] for w in query('aerospace','list-workspaces','--monitor','all','--visible','--json')}
            windows=[dict(id=w['window-id'],pid=w['app-pid'],workspace=int(w['workspace']) if str(w['workspace']).isdigit() else None,
                display=ids[w['monitor-id']],frame=frames[w['window-id']],focused=w['window-id']==focused,
                floating=w['window-layout']=='floating',visible=w['workspace'] in visible)
                for w in rows if w['window-id'] in frames]
            displays=geometry['displays']
        return dict(windows=windows,displays=sorted(displays,key=lambda d:(d['frame']['x'],d['frame']['y'])))

    def focus(self,w):
        if self.name=='rift':
            rift.focus_window(next(x for x in rift.snapshot()['windows'] if x['id']==w['id']))
        elif self.name=='yabai': run('yabai','-m','window','--focus',w['id'])
        else: run('aerospace','focus','--window-id',w['id'])
        self.wait(lambda s:any(x['id']==w['id'] and x['focused'] for x in s['windows']))

    def workspace(self,n):
        if self.name=='rift':run(sys.executable,ROOT/'wm_rift.py','action','workspace',n)
        elif self.name=='yabai':run(sys.executable,ROOT/'yabai/.config/yabai/scripts/focus-space.py','ws'+str(n))
        else:run('aerospace','workspace',n)

    def visible_workspaces(self):
        if self.name=='rift':
            return [next(w['index']+1 for w in rift.query('workspaces',d['space']) if w['is_active'])
                    for d in rift.query('displays') if d.get('space')]
        if self.name=='yabai':
            return [int(s['label'][2:]) for s in query('yabai','-m','query','--spaces')
                    if s['is-visible'] and re.fullmatch(r'ws[1-9]',s['label'])]
        return [int(w['workspace']) for w in query('aerospace','list-workspaces','--monitor','all','--visible','--json')
                if str(w['workspace']).isdigit()]

    def layout_matches(self,mode):
        if self.name=='rift':return rift.current_slot()[1]['layout_mode']==mode
        if self.name=='yabai':return query('yabai','-m','query','--spaces','--space')['type']==mode
        rows=query('aerospace','list-windows','--focused','--json','--format','%{window-layout}')
        return bool(rows) and rows[0]['window-layout'].endswith('accordion' if mode=='stack' else 'tiles')

    def active_workspace(self):
        if self.name=='rift':return rift.current_slot()[1]['index']+1
        if self.name=='yabai':
            label=query('yabai','-m','query','--spaces','--space')['label']
            return int(label[2:]) if re.fullmatch(r'ws[1-9]',label) else None
        rows=query('aerospace','list-workspaces','--focused','--json')
        return int(rows[0]['workspace']) if rows else None

    def action(self,kind,*args):
        if self.name=='rift':return run(sys.executable,ROOT/'wm_rift.py','action',kind,*args)
        if kind in ('focus','move'):
            return run(sys.executable,ROOT/'wm-direction.py',self.name,args[0],*(['--focus'] if kind=='focus' else []))
        if kind=='resize':
            if self.name=='yabai':return run(sys.executable,ROOT/'wm-resize.py',*args)
            return run('aerospace','resize',args[0],f'{int(args[1]):+d}')
        if kind=='preset':return run(sys.executable,ROOT/'wm-size.py',self.name,*args)
        if kind=='float':return run(sys.executable,ROOT/'wm-float.py') if self.name=='yabai' else run(ROOT/'aerospace-float-toggle.sh')
        if kind=='send':
            if self.name=='yabai':
                run('yabai','-m','window','--space','ws'+str(args[0]))
                if '--follow' in args:self.workspace(args[0])
            else:run('aerospace','move-node-to-workspace',args[0],*(['--focus-follows-window'] if '--follow' in args else []))

    def layout(self,mode):
        if self.name=='rift':run('rift-cli','execute','workspace','set-layout',mode)
        elif self.name=='yabai':run('yabai','-m','space','--layout',mode)
        else:run('aerospace','layout','accordion' if mode=='stack' else 'tiles')

    def split(self):
        if self.name=='rift':run('rift-cli','execute','layout','toggle-orientation')
        elif self.name=='yabai':run('yabai','-m','window','--toggle','split')
        else:run('aerospace','layout','horizontal','vertical')

    def wait(self,predicate,timeout=4):
        until=time.monotonic()+timeout
        matched=False
        while True:
            state=self.snapshot()
            self.last_state=state
            current=predicate(state)
            if current and matched:return state
            matched=current
            if time.monotonic()>until:raise RuntimeError('Final window state did not match the expected behavior')
            time.sleep(.08)

    def side(self,selected,side):
        self.focus(selected)
        if self.name=='rift':
            ws=rift.snapshot()['windows'];w=next(w for w in ws if w['id']==selected['id'])
            rift_geometry.place_side(rift,w,[x for x in ws if x['workspace']==w['workspace'] and x['display']==w['display'] and not x['floating']],side)
        elif self.name=='yabai':
            w=direction.query('--windows','--window',selected['id'])
            direction.place_yabai_side(w,direction.query('--windows','--space',w['space']),side)
        else:
            run('aerospace','flatten-workspace-tree','--workspace',selected['workspace'])
            run('aerospace','layout','--workspace',selected['workspace'],'--root','v_tiles' if side in ('left','right') else 'h_tiles')
            run('aerospace','move','--window-id',selected['id'],'--boundaries','workspace','--boundaries-action','create-implicit-container',side)


def build_fixture(folder):
    source=folder/'Windows.swift';binary=folder/'LayoutCheck'
    source.write_text('''import Cocoa
let app = NSApplication.shared
app.setActivationPolicy(.regular)
var windows: [NSWindow] = []
for i in 0..<3 {
 let window = NSWindow(contentRect: NSRect(x: 100+i*100,y: 100+i*100,width: 500,height: 400),styleMask: [.titled,.closable,.resizable,.miniaturizable],backing: .buffered,defer: false)
 window.title = "Window manager benchmark \\(i+1)"
 window.isReleasedWhenClosed = false
 window.makeKeyAndOrderFront(nil)
 windows.append(window)
}
app.activate(ignoringOtherApps: true)
app.run()
''')
    run('/usr/bin/swiftc',source,'-o',binary)
    binaries={}
    for number in (5,6):
        bundle=folder/f'Fixture{number}.app'/'Contents'
        (bundle/'MacOS').mkdir(parents=True)
        (bundle/'Info.plist').write_bytes(plistlib.dumps(dict(
            CFBundleExecutable='LayoutCheck',CFBundleIdentifier=f'local.dotfiles.benchmark.fixture{number}',
            CFBundleName=f'WM fixture {number}',CFBundlePackageType='APPL')))
        binaries[number]=bundle/'MacOS/LayoutCheck'
        shutil.copy2(binary,binaries[number])
    return binaries


def benchmark(name,binary,repeats,idle_seconds):
    backend=Backend(name);apps=[];cases=[]
    record=dict(manager=name,cases=cases)
    start=time.monotonic();run(ROOT/'wm.sh','use',name,'--temporary');record['switch_seconds']=time.monotonic()-start
    original=backend.snapshot();focus=next((w for w in original['windows'] if w['focused']),None)
    visible=backend.visible_workspaces()
    record['displays']=original['displays']
    if [d['frame'] for d in original['displays']] != [dict(x=0,y=0,w=2560,h=1440),dict(x=2560,y=0,w=2560,h=1440)]:
        raise RuntimeError('This benchmark expects the recorded pair of 2560x1440 external displays')
    if any(w['workspace'] in (5,6) for w in original['windows']):
        raise RuntimeError('Workspaces 5 and 6 must be empty before benchmarking')
    def fixture(number=5):return [w for w in backend.snapshot()['windows'] if w['pid'] in {a.pid for a in apps} and w['workspace']==number]
    def measured(label,action,expected,details=None):
        case=dict(name=label,details=details or {})
        case['before_windows']=[w for w in backend.snapshot()['windows'] if w['pid'] in {a.pid for a in apps}]
        begin=time.perf_counter()
        try:
            action();case['command_ms']=(time.perf_counter()-begin)*1000
            state=backend.wait(expected)
            case.update(passed=True,verified_ms=(time.perf_counter()-begin)*1000)
            case['result_windows']=[w for w in state['windows'] if w['pid'] in {a.pid for a in apps}]
        except Exception as error:
            case.update(passed=False,error=str(error),elapsed_ms=(time.perf_counter()-begin)*1000)
            case['result_windows']=[w for w in getattr(backend,'last_state',{}).get('windows',[]) if w['pid'] in {a.pid for a in apps}]
        try:
            case['native_observation']=query('/usr/bin/osascript','-l','JavaScript',ROOT/'scripts/wm/observe-benchmark-windows.js',json.dumps([a.pid for a in apps]))
            focused=next((w for w in case.get('result_windows',[]) if w['focused']),None)
            if focused:
                native=case['native_observation']
                case['native_focus_matches']=native.get('focused_id')==focused['id']
        except Exception as error:
            case['native_observation_error']=str(error)
        cases.append(case)
        print(name,label,'PASS' if case['passed'] else 'FAIL: '+case['error'],flush=True)
        return case['passed']
    try:
        for number in (5,6):
            backend.workspace(number);app=subprocess.Popen([str(binary[number])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(app)
            backend.wait(lambda s:len([w for w in s['windows'] if w['pid']==app.pid])==3)
            backend.wait(lambda s:any(w['pid']==app.pid and w['focused'] for w in s['windows']))
            validate_fixture(backend.snapshot(),{a.pid:n for a,n in zip(apps,(5,6))})
        record['fixture_window_count']=sum(len(fixture(n)) for n in (5,6))
        backend.workspace(5)
        validate_fixture(backend.snapshot(),{a.pid:n for a,n in zip(apps,(5,6))})
        with Resources(name) as idle:time.sleep(idle_seconds)
        record['idle']=idle.result()
        with Resources(name) as active:
            for i in range(repeats):
                n=6 if i%2==0 else 5
                measured('workspace_switch',lambda n=n:backend.workspace(n),
                         lambda s,n=n:any(w['workspace']==n and w['focused'] for w in s['windows']),dict(target=n))
            backend.workspace(5)
            for i in range(repeats):
                ws=fixture(); selected=ws[i%len(ws)]; backend.focus(selected)
                ws=fixture();selected=next(w for w in ws if w['id']==selected['id'])
                candidates=[(d,direction.neighbor(selected,ws,d,allow_overlap=True)) for d in ('left','right','up','down')]
                d,target=next((d,w) for d,w in candidates if w)
                measured('directional_focus',lambda d=d:backend.action('focus',d),
                         lambda s,wid=target['id']:any(w['id']==wid and w['focused'] for w in s['windows']),dict(direction=d))
            for i in range(max(3,repeats//3)):
                ws=fixture();selected=ws[0];backend.side(selected,'right');ws=fixture()
                selected=min(ws,key=lambda w:(w['frame']['x'],w['frame']['y']));backend.focus(selected)
                measured('expand_into_side',lambda:backend.action('move','left'),
                    lambda s,wid=selected['id']:any(w['id']==wid and w['workspace']==5 and w['frame']['h']>1300 and 1200<w['frame']['w']<1300 for w in s['windows']))
                selected=next(w for w in fixture() if w['id']==selected['id']);backend.focus(selected)
                for delta in (32,-32):
                    old=next(w for w in fixture() if w['id']==selected['id'])['frame']['w']
                    measured('resize_width',lambda delta=delta:backend.action('resize','width',delta),
                        lambda s,wid=selected['id'],old=old,delta=delta:any(w['id']==wid and abs(w['frame']['w']-old-delta)<=2 for w in s['windows']),dict(delta=delta))
                before={w['id']:w['frame'] for w in fixture()}
                target=direction.neighbor(selected,fixture(),'right',allow_overlap=True)
                if target:
                    measured('neighbor_swap',lambda:backend.action('move','right'),
                        lambda s,a=selected['id'],b=target['id']:all(any(w['id']==wid and abs(w['frame']['x']-before[other]['x'])<=2 and abs(w['frame']['y']-before[other]['y'])<=2 for w in s['windows']) for wid,other in ((a,b),(b,a))))
            ws=fixture();selected=ws[0];backend.side(selected,'right');backend.focus(selected)
            backend.wait(lambda s:any(w['id']==selected['id'] and abs(w['frame']['w']-2525*.5)<=3 for w in s['windows']))
            for step,fraction in [('up',.65),('up',.75),('down',.65),('down',.5)]:
                measured('width_preset',lambda step=step:backend.action('preset',step),
                    lambda s,wid=selected['id'],fraction=fraction:any(w['id']==wid and abs(w['frame']['w']-2525*fraction)<=3 for w in s['windows']),dict(step=step,fraction=fraction))
            ws=fixture();row=min(ws,key=lambda w:w['frame']['h']);backend.focus(row)
            for delta in (32,-32):
                old=next(w for w in fixture() if w['id']==row['id'])['frame']['h']
                measured('resize_height',lambda delta=delta:backend.action('resize','height',delta),
                    lambda s,wid=row['id'],old=old,delta=delta:any(w['id']==wid and abs(w['frame']['h']-old-delta)<=2 for w in s['windows']),dict(delta=delta))
            selected=fixture()[0];backend.focus(selected)
            floating_frame=None
            for floating in (True,False,True,False):
                measured('float_toggle',lambda:backend.action('float'),
                    lambda s,wid=selected['id'],floating=floating:any(w['id']==wid and w['floating']==floating and
                        (not floating or floating_frame is None or all(abs(w['frame'][k]-floating_frame[k])<=2 for k in ('x','y','w','h')))
                        for w in s['windows']),dict(floating=floating,restores_geometry=floating_frame is not None))
                if floating and floating_frame is None:
                    floating_frame=next(w for w in fixture() if w['id']==selected['id'])['frame']
            # Verify the engine mode and preserve geometry for independent inspection.
            for mode in ('stack','bsp'):
                measured('layout_change',lambda mode=mode:backend.layout(mode),
                    lambda s,mode=mode:len([w for w in s['windows'] if w['pid']==apps[0].pid])==3 and backend.layout_matches(mode),
                    dict(layout=mode,validation='engine mode, intact membership, saved resulting geometry'))
            backend.side(fixture()[0],'right');selected=next(w for w in fixture() if w['frame']['h']>1300);backend.focus(selected)
            before={w['id']:w['frame'] for w in fixture()}
            measured('split_orientation',backend.split,
                lambda s:any(w['id'] in before and abs(w['frame']['w']-before[w['id']]['w'])>10 for w in s['windows']))
            backend.side(fixture()[0],'right');selected=next(w for w in fixture() if w['frame']['h']>1300);backend.focus(selected)
            measured('cross_monitor_focus',lambda:backend.action('focus','right'),
                lambda s:any(w['pid']==apps[1].pid and w['focused'] for w in s['windows']))
            backend.workspace(5);backend.focus(selected)
            measured('cross_monitor_move',lambda:backend.action('move','right'),
                lambda s,wid=selected['id']:any(w['id']==wid and w['workspace']==6 and abs(w['frame']['x']-2570)<=2 and w['frame']['h']>1300 and 1200<w['frame']['w']<1300 for w in s['windows']),dict(direction='right',expected='incoming left half with normal gaps'))
            current=next(w for w in backend.snapshot()['windows'] if w['id']==selected['id'])
            if current['workspace']==6:
                backend.focus(current)
                measured('cross_monitor_focus',lambda:backend.action('focus','left'),
                    lambda s:any(w['workspace']==5 and w['focused'] for w in s['windows']),dict(direction='left'))
                backend.focus(current)
                measured('cross_monitor_move',lambda:backend.action('move','left'),
                    lambda s,wid=selected['id']:any(w['id']==wid and w['workspace']==5 and abs(w['frame']['x']-1288)<=2 and w['frame']['h']>1300 and 1200<w['frame']['w']<1300 for w in s['windows']),dict(direction='left',expected='incoming right half with normal gaps'))
            # Restore this fixture window before send/follow checks.
            current=next(w for w in backend.snapshot()['windows'] if w['id']==selected['id']);backend.focus(current)
            if current['workspace']!=5:backend.action('send',5,'--follow')
            for follow in (False,True):
                backend.workspace(5);backend.focus(selected)
                measured('workspace_send_follow' if follow else 'workspace_send_stay',
                    lambda follow=follow:backend.action('send',6,*(['--follow'] if follow else [])),
                    lambda s,wid=selected['id'],follow=follow:any(w['id']==wid and w['workspace']==6 for w in s['windows']) and
                        any(w['focused'] and w['workspace']==(6 if follow else 5) for w in s['windows']))
                backend.workspace(6);current=next(w for w in backend.snapshot()['windows'] if w['id']==selected['id']);backend.focus(current);backend.action('send',5,'--follow')
            apps[1].terminate();apps[1].wait(timeout=3)
            backend.workspace(5);backend.side(fixture()[0],'right')
            selected=next(w for w in fixture() if w['frame']['h']>1300);backend.focus(selected)
            measured('focus_empty_monitor',lambda:backend.action('focus','right'),
                     lambda s:backend.active_workspace()==6)
        record['active']=active.result()
    except Exception as error:
        record['setup_or_cleanup_error']=str(error)
        if 'active' in locals() and active.samples:record['active']=active.result()
    finally:
        for app in apps:
            app.terminate()
            try:app.wait(timeout=3)
            except subprocess.TimeoutExpired:app.kill();app.wait()
        for number in visible:
            try:backend.workspace(number)
            except Exception as error:record.setdefault('restore_workspace_errors',[]).append(str(error))
        if focus:
            try:backend.workspace(focus['workspace']);backend.focus(focus)
            except Exception as error:record['restore_focus_error']=str(error)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--managers',nargs='+',default=['yabai','rift','aerospace'],choices=['yabai','rift','aerospace'])
    parser.add_argument('--repeats',type=int,default=12)
    parser.add_argument('--idle-seconds',type=float,default=8)
    parser.add_argument('--run-live',action='store_true')
    parser.add_argument('--rounds',type=int,default=2)
    args=parser.parse_args()
    if not args.run_live:parser.error('Pass --run-live only with empty workspaces 5/6 and an idle keyboard/mouse')
    original=run(ROOT/'wm.sh','current').strip()
    original_backend=Backend(original)
    original_visible=original_backend.visible_workspaces()
    original_focus=next((w for w in original_backend.snapshot()['windows'] if w['focused']),None)
    parked=[w for w in original_backend.snapshot()['windows'] if w['workspace'] in (5,6)]
    data=dict(created_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),os=run('sw_vers'),
              chip=run('sysctl','-n','machdep.cpu.brand_string').strip(),memory_bytes=int(run('sysctl','-n','hw.memsize')),
              original_manager=original,saved_default_before=run(ROOT/'wm.sh','default','status').strip(),runs=[],
              temporarily_parked_windows=[dict(id=w['id'],pid=w['pid'],workspace=w['workspace']) for w in parked],
              method=dict(rounds=args.rounds,repeats=args.repeats,idle_seconds=args.idle_seconds,sample_interval_seconds=.2,
                          timing='command completion and separately verified state; includes adapter overhead',
                          cpu='ps cumulative CPU deltas, one-core percent; short-lived helpers can be missed between samples',
                          geometry='two 2560x1440 external displays; 15px inner gaps, 10px sides, 50px top, 8px bottom',
                          revision=2, fixture='two distinct app bundles, three windows each',
                          verification='two matching backend states, then independent CoreGraphics/AX focus observation; native audit is outside latency timing'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():args.output.write_text(json.dumps(data,indent=2))
    try:
        for window in parked:
            original_backend.workspace(window['workspace']);original_backend.focus(window)
            original_backend.action('send',window['workspace']-2)
        if original_focus:
            original_backend.workspace(original_focus['workspace']);original_backend.focus(original_focus)
        with tempfile.TemporaryDirectory(prefix='wm-benchmark-') as temp:
            binary=build_fixture(Path(temp))
            for round_number in range(args.rounds):
                order=args.managers if round_number%2==0 else list(reversed(args.managers))
                for manager in order:
                    print('Starting',manager,'round',round_number+1,flush=True)
                    try:
                        record=benchmark(manager,binary,args.repeats,args.idle_seconds)
                        record['version']=run(manager if manager!='rift' else str(Path.home()/'.local/bin/rift'),'--version').strip()
                    except Exception as error:
                        record=dict(manager=manager,cases=[],setup_or_cleanup_error=str(error))
                    record['round']=round_number+1
                    data['runs'].append(record);save()
            data['extra_lifecycle_checks']=[]
            for manager in ('aerospace','yabai'):
                previous=run(ROOT/'wm.sh','current').strip()
                try:
                    begin=time.monotonic();run(ROOT/'wm.sh','use',manager,'--temporary')
                    actual=run(ROOT/'wm.sh','current').strip()
                    data['extra_lifecycle_checks'].append(dict(source=previous,target=manager,passed=actual==manager,seconds=time.monotonic()-begin))
                except Exception as error:
                    data['extra_lifecycle_checks'].append(dict(source=previous,target=manager,passed=False,error=str(error)))
                save()
    finally:
        if original in ('yabai','rift','aerospace'):
            try:
                run(ROOT/'wm.sh','use',original,'--temporary')
                for window in parked:
                    current=next((w for w in original_backend.snapshot()['windows'] if w['id']==window['id'] and w['pid']==window['pid']),None)
                    if current:
                        original_backend.workspace(current['workspace']);original_backend.focus(current)
                        original_backend.action('send',window['workspace'])
                for number in original_visible:original_backend.workspace(number)
                if original_focus:original_backend.focus(original_focus)
            except Exception as error:data['restore_manager_error']=str(error)
        data['saved_default_after']=run(ROOT/'wm.sh','default','status').strip()
        save()
    print('Raw results:',args.output)


if __name__=='__main__':main()
