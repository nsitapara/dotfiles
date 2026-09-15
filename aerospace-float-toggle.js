// Keep restoreFrame in sync with wm-float.py; parity is checked by tests.
function valid(frame) {
    return frame && ['x', 'y', 'w', 'h'].every(k => Number.isFinite(frame[k])) && frame.w > 0 && frame.h > 0;
}

function restoreFrame(saved, area, scale) {
    if (!saved || !valid(saved.frame) || !valid(saved.area)) {
        const w = area.w * scale, h = area.h * scale;
        return {x: Math.round(area.x + (area.w - w)/2), y: Math.round(area.y + (area.h - h)/2),
                w: Math.round(w), h: Math.round(h)};
    }
    const f = saved.frame, old = saved.area;
    const w = Math.min(f.w, area.w), h = Math.min(f.h, area.h);
    const x = area.x + (f.x - old.x) * area.w / old.w;
    const y = area.y + (f.y - old.y) * area.h / old.h;
    return {x: Math.round(Math.max(area.x, Math.min(x, area.x + area.w - w))),
            y: Math.round(Math.max(area.y, Math.min(y, area.y + area.h - h))), w: Math.round(w), h: Math.round(h)};
}

function run() {
    ObjC.import('Cocoa');
    ObjC.import('CoreGraphics');
    function command(args) {
        const task = $.NSTask.alloc.init, out = $.NSPipe.pipe, err = $.NSPipe.pipe;
        task.launchPath = '/opt/homebrew/bin/aerospace';
        task.arguments = args;
        task.standardOutput = out; task.standardError = err;
        task.launch;
        const data = out.fileHandleForReading.readDataToEndOfFile;
        task.waitUntilExit;
        if (task.terminationStatus !== 0) {
            const message = $.NSString.alloc.initWithDataEncoding(err.fileHandleForReading.readDataToEndOfFile, $.NSUTF8StringEncoding).js;
            throw Error(message || 'AeroSpace command failed');
        }
        return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
    }
    const rows = JSON.parse(command(['list-windows', '--focused', '--json', '--format',
        '%{window-id} %{window-layout} %{app-pid} %{window-is-fullscreen}']));
    if (!rows.length) return;
    const selected = rows[0], id = selected['window-id'], pid = selected['app-pid'];
    if (selected['window-is-fullscreen']) throw Error('Leave fullscreen before toggling floating');
    const proc = Application('System Events').processes.whose({unixId: pid})[0];
    const win = proc.attributes.byName('AXFocusedWindow').value();
    const pos = win.position(), size = win.size();
    const cg = ObjC.deepUnwrap($.CGWindowListCopyWindowInfo($.kCGWindowListOptionIncludingWindow, id))[0];
    if (!cg || cg.kCGWindowOwnerPID !== pid ||
        Math.abs(cg.kCGWindowBounds.X - pos[0]) > 2 || Math.abs(cg.kCGWindowBounds.Y - pos[1]) > 2 ||
        Math.abs(cg.kCGWindowBounds.Width - size[0]) > 2 || Math.abs(cg.kCGWindowBounds.Height - size[1]) > 2) {
        throw Error('Window focus changed; retry the float shortcut');
    }
    const primaryH = $.NSScreen.screens.js[0].frame.size.height;
    const cx = pos[0] + size[0]/2, cy = primaryH - pos[1] - size[1]/2;
    const screen = $.NSScreen.screens.js.find(s => {
        const f = s.frame;
        return cx >= f.origin.x && cx < f.origin.x + f.size.width && cy >= f.origin.y && cy < f.origin.y + f.size.height;
    });
    if (!screen) throw Error('Window monitor is unavailable');
    const vf = screen.visibleFrame;
    const inset = /built-in/i.test(screen.localizedName.js) ? 16 : 50;
    const area = {x: vf.origin.x, y: primaryH - vf.origin.y - vf.size.height + inset,
                  w: vf.size.width, h: vf.size.height - inset};
    const directory = $.NSHomeDirectory().js + '/.local/state/dotfiles-wm';
    const path = directory + '/float-frames.json';
    let cache = {};
    try {
        cache = JSON.parse($.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null).js);
        if (!cache || Array.isArray(cache) || typeof cache !== 'object') cache = {};
    } catch (_) { cache = {}; }
    Object.keys(cache).forEach(k => {
        if (!cache[k] || typeof cache[k] !== 'object' || !Number.isFinite(cache[k].at)) delete cache[k];
    });
    const key = pid + ':' + id;
    if (selected['window-layout'] === 'floating') {
        cache[key] = {frame: {x:pos[0], y:pos[1], w:size[0], h:size[1]}, area:area, at:Date.now()/1000};
        Object.keys(cache).sort((a,b) => (cache[a].at || 0) - (cache[b].at || 0)).slice(0, -200).forEach(k => delete cache[k]);
        $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(directory, true, null, null);
        if (!$(JSON.stringify(cache)).writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null)) {
            throw Error('Could not save floating window position');
        }
        command(['layout', '--window-id', String(id), 'tiling']);
    } else {
        const frame = restoreFrame(cache[key], area, 0.95);
        command(['layout', '--window-id', String(id), 'floating']);
        win.position = [frame.x, frame.y];
        win.size = [frame.w, frame.h];
        win.position = [frame.x, frame.y];
    }
}

if (typeof module !== 'undefined') module.exports = {restoreFrame};
