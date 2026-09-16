// Read only. Retain fixture identities and geometry, never titles or other apps.
function run(argv) {
    ObjC.import('Cocoa');
    ObjC.import('CoreGraphics');
    const pids = JSON.parse(argv[0]);
    const info = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll, 0)));
    const windows = info.filter(w => pids.includes(w.kCGWindowOwnerPID) && w.kCGWindowLayer === 0).map(w => ({
        id: w.kCGWindowNumber, pid: w.kCGWindowOwnerPID,
        frame: {x: w.kCGWindowBounds.X, y: w.kCGWindowBounds.Y, w: w.kCGWindowBounds.Width, h: w.kCGWindowBounds.Height},
        onscreen: !!w.kCGWindowIsOnscreen
    }));
    const pid = Number($.NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier);
    let focused = null, error = null;
    if (pids.includes(pid)) {
        try {
            const proc = Application('System Events').processes.whose({unixId: pid})[0];
            const win = proc.attributes.byName('AXFocusedWindow').value();
            const p = win.position(), s = win.size();
            const matches = windows.filter(w => w.pid === pid && Math.abs(w.frame.x-p[0]) <= 2 &&
                Math.abs(w.frame.y-p[1]) <= 2 && Math.abs(w.frame.w-s[0]) <= 2 && Math.abs(w.frame.h-s[1]) <= 2);
            if (matches.length === 1) focused = matches[0].id;
            else error = 'AX geometry does not uniquely identify a fixture window';
        } catch (e) { error = String(e); }
    }
    return JSON.stringify({windows, focused_id: focused, frontmost_fixture_pid: pids.includes(pid) ? pid : null, focus_error: error});
}
