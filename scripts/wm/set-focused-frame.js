// Public Accessibility API. Check the focused window's process and CG bounds
// before changing geometry, so an intervening focus change cannot resize an app.
function run(argv) {
    ObjC.import('Cocoa');
    ObjC.import('CoreGraphics');
    const target = JSON.parse(argv[0]), frame = target.frame;
    const proc = Application('System Events').processes.whose({unixId: target.pid})[0];
    const win = proc.attributes.byName('AXFocusedWindow').value();
    const pos = win.position(), size = win.size();
    const info = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionIncludingWindow, target.id)));
    const cg = info && info[0];
    if (!cg || cg.kCGWindowOwnerPID !== target.pid ||
        Math.abs(cg.kCGWindowBounds.X-pos[0]) > 2 || Math.abs(cg.kCGWindowBounds.Y-pos[1]) > 2 ||
        Math.abs(cg.kCGWindowBounds.Width-size[0]) > 2 || Math.abs(cg.kCGWindowBounds.Height-size[1]) > 2) {
        throw Error('Window focus changed; retry the shortcut');
    }
    win.position = [frame.x, frame.y];
    win.size = [frame.w, frame.h];
    win.position = [frame.x, frame.y];
}
