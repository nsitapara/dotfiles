import AppKit
import Darwin

// Pointer polling requires neither Accessibility nor Input Monitoring access.
// Window metadata keeps the bar hidden while a native dropdown is open.
let args = CommandLine.arguments
guard args.count == 4, let barPID = Int32(args[2]), barPID > 0 else {
    fputs("Usage: sbar-hover SKETCHYBAR_PATH BAR_PID LOCK_FILE\n", stderr)
    exit(1)
}
let barPath = args[1]
let lockFD = open(args[3], O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
guard lockFD >= 0 else { exit(1) }
// A replacement waits for the previous helper to restore the bar before exiting.
guard flock(lockFD, LOCK_EX) == 0 else { exit(1) }
signal(SIGCHLD, SIG_DFL)
signal(SIGTERM, SIG_IGN)
signal(SIGINT, SIG_IGN)
signal(SIGUSR1, SIG_IGN)

func bar(_ arguments: [String]) {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: barPath)
    task.arguments = arguments
    task.standardOutput = FileHandle.nullDevice
    task.standardError = FileHandle.nullDevice
    do {
        try task.run()
        task.waitUntilExit()
    } catch {
        fputs("SketchyBar hover: \(error)\n", stderr)
    }
}

// Private SkyLight call (also used by the SketchyBar menus helper) that sets
// the native menu bar's opacity without changing whether macOS reveals it.
@_silgen_name("SLSMainConnectionID") func SLSMainConnectionID() -> Int32
@_silgen_name("SLSSetMenuBarInsetAndAlpha")
func SLSSetMenuBarInsetAndAlpha(_ cid: Int32, _ u1: Double, _ u2: Double, _ alpha: Float)
func setNativeMenuAlpha(_ alpha: Float) {
    SLSSetMenuBarInsetAndAlpha(SLSMainConnectionID(), 0, 1, alpha)
}

func restore() {
    setNativeMenuAlpha(1)
    bar(["--bar", "topmost=off", "hidden=off", "y_offset=0"])
}

func menuVisibility() -> (native: Bool, popup: Bool) {
    guard let windows = CGWindowListCopyWindowInfo(.optionOnScreenOnly, 0)
            as? [[String: Any]] else { return (false, false) }
    var native = false
    var popup = false
    for window in windows {
        guard let number = window[kCGWindowLayer as String] as? NSNumber,
              let bounds = window[kCGWindowBounds as String] as? NSDictionary,
              let frame = CGRect(dictionaryRepresentation: bounds) else { continue }
        // macOS 27 marks some layers with bit 31. Ignore it when matching.
        let layer = number.int64Value & Int64(0x7fff_ffff)
        let owner = window[kCGWindowOwnerName as String] as? String
        if layer == 24 && owner == "Window Server"
            && frame.height > 0 && frame.height <= 100 && frame.width > 100 {
            native = true
        }
        let pid = (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value ?? 0
        let alpha = (window[kCGWindowAlpha as String] as? NSNumber)?.doubleValue ?? 0
        if isSketchyBarPopup(ownerPID: pid, layer: layer, frame: frame, alpha: alpha,
                            barPID: barPID, displayBounds: displayBounds) {
            popup = true
        }
    }
    return (native, popup)
}

var signalSources: [DispatchSourceSignal] = []
for sig in [SIGTERM, SIGINT] {
    let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    source.setEventHandler { restore(); exit(0) }
    source.resume()
    signalSources.append(source)
}

var state = HoverState()
var menus = (native: false, popup: false)
var masked = false
// Screen geometry queries round-trip to the window server; refresh once a second
// instead of on every pointer tick. Auto-hide can report a zero visible-frame
// inset, so keep at least 36pt as the menu zone, or the notch's safe area.
struct ScreenInfo { let frame: CGRect; let menuHeight: Int }
var screens: [ScreenInfo] = []
var displayBounds: [CGRect] = []
func refreshScreens() {
    displayBounds = NSScreen.screens.compactMap { screen in
        guard let id = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else { return nil }
        return CGDisplayBounds(id.uint32Value)
    }
    screens = NSScreen.screens.map {
        ScreenInfo(frame: $0.frame, menuHeight: Int(ceil(max(36, $0.safeAreaInsets.top))))
    }
}
refreshScreens()
setNativeMenuAlpha(1) // In case a previous helper died while masking it.
// Keep item windows above the native menu hit area. At floating-window level
// the first click after using another app can land on that area instead.
bar(["--bar", "topmost=on", "hidden=off", "y_offset=0"])
// Poll the pointer at 30 Hz near the top or while a hand-off is in progress,
// and at 10 Hz otherwise: that is enough to see it heading for the top before
// macOS starts revealing its menu bar.
let fastInterval = DispatchTimeInterval.milliseconds(33)
let slowInterval = DispatchTimeInterval.milliseconds(100)
let fastZone = 200.0
var fast = true
var lastScreenRefresh = 0.0
var lastMenuCheck = 0.0
let timer = DispatchSource.makeTimerSource(queue: .main)
timer.schedule(deadline: .now(), repeating: fastInterval, leeway: .milliseconds(5))
timer.setEventHandler {
    autoreleasepool {
        let now = ProcessInfo.processInfo.systemUptime
        if now - lastScreenRefresh >= 1 {
            lastScreenRefresh = now
            if kill(barPID, 0) != 0 { exit(0) }
            refreshScreens()
        }
        let pointer = NSEvent.mouseLocation
        let screen = screens.first { $0.frame.insetBy(dx: -1, dy: -1).contains(pointer) }
        let distance = screen.map { Double($0.frame.maxY - pointer.y) }
        let menuHeight = screen?.menuHeight ?? 36
        // The window-list query is the costly part. Poll it every tick only while
        // the pointer is in the menu zone so the hide lands as the bar appears,
        // 10 Hz while hidden to notice the menu closing, and 1 Hz otherwise for
        // keyboard-driven menu activation while the pointer is elsewhere.
        let nearTop = distance.map { $0 >= 0 && $0 <= Double(menuHeight) } ?? false
        let menuEvery = nearTop ? 0 : ((state.hidden || menus.popup) ? 0.1 : 1.0)
        if now - lastMenuCheck >= menuEvery {
            lastMenuCheck = now
            menus = menuVisibility()
        }
        let change = state.update(distance: distance, menuHeight: menuHeight,
                                  mouseDown: NSEvent.pressedMouseButtons != 0,
                                  menuVisible: menus.native, now: now, popupVisible: menus.popup)
        let wantFast = state.hidden || state.maskNative
            || (distance.map { $0 >= 0 && $0 <= fastZone } ?? false)
        if wantFast != fast {
            fast = wantFast
            let interval = fast ? fastInterval : slowInterval
            timer.schedule(deadline: .now() + interval, repeating: interval,
                           leeway: .milliseconds(fast ? 5 : 20))
        }
        // Keep the native bar transparent while the reveal delay runs, then
        // restore it for the handoff. Reassert each tick: other tools reset it.
        if state.maskNative || state.maskNative != masked {
            masked = state.maskNative
            setNativeMenuAlpha(masked ? 0 : 1)
        }
        if let hidden = change {
            bar(["--bar", "hidden=\(hidden ? "on" : "off")", "y_offset=0"])
        }
    }
}
// The corner icon signals this existing helper so it owns the handoff state.
// Merely hiding the bar from Lua would leave the hover timer masking the menu.
let appleMenuSignal = DispatchSource.makeSignalSource(signal: SIGUSR1, queue: .main)
appleMenuSignal.setEventHandler {
    state.revealNativeMenu()
    masked = false
    setNativeMenuAlpha(1)
    bar(["--bar", "hidden=on", "y_offset=0"])
    let menu = Process()
    menu.executableURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".config/sketchybar/helpers/menus/bin/menus")
    menu.arguments = ["-s", "0"] // first native menu item is Apple
    menu.standardOutput = FileHandle.nullDevice
    do { try menu.run() }
    catch { fputs("SketchyBar Apple menu: \(error)\n", stderr) }
}
appleMenuSignal.resume()
signalSources.append(appleMenuSignal)
timer.resume()
RunLoop.main.run()
