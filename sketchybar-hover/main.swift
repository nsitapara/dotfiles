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

func nativeMenuVisible() -> Bool {
    guard let windows = CGWindowListCopyWindowInfo(.optionOnScreenOnly, 0)
            as? [[String: Any]] else { return false }
    for window in windows {
        // macOS 27 marks some layers with bit 31. Ignore it when matching.
        guard let number = window[kCGWindowLayer as String] as? NSNumber else { continue }
        let layer: Int64 = number.int64Value & Int64(0x7fff_ffff)
        guard layer == 24 else { continue }
        let owner = window[kCGWindowOwnerName as String] as? String
        guard owner == "Window Server" else { continue }
        guard let bounds = window[kCGWindowBounds as String] as? [String: Any],
              let height = bounds["Height"] as? NSNumber,
              let width = bounds["Width"] as? NSNumber else { continue }
        if height.doubleValue > 0 && height.doubleValue <= 100 && width.doubleValue > 100 {
            return true
        }
    }
    return false
}

var signalSources: [DispatchSourceSignal] = []
for sig in [SIGTERM, SIGINT] {
    let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    source.setEventHandler { restore(); exit(0) }
    source.resume()
    signalSources.append(source)
}

var state = HoverState()
var menuVisible = false
var masked = false
// Screen geometry queries round-trip to the window server; refresh once a second
// instead of on every pointer tick. Auto-hide can report a zero visible-frame
// inset, so keep at least 36pt as the menu zone, or the notch's safe area.
struct ScreenInfo { let frame: CGRect; let menuHeight: Int }
var screens: [ScreenInfo] = []
func refreshScreens() {
    screens = NSScreen.screens.map {
        ScreenInfo(frame: $0.frame, menuHeight: Int(ceil(max(36, $0.safeAreaInsets.top))))
    }
}
refreshScreens()
setNativeMenuAlpha(1) // In case a previous helper died while masking it.
bar(["--bar", "topmost=window", "hidden=off", "y_offset=0"])
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
        // keyboard-driven menu activation (the native bar already draws on top,
        // so a late hide is invisible).
        let nearTop = distance.map { $0 >= 0 && $0 <= Double(menuHeight) } ?? false
        let menuEvery = nearTop ? 0 : (state.hidden ? 0.1 : 1.0)
        if now - lastMenuCheck >= menuEvery {
            lastMenuCheck = now
            menuVisible = nativeMenuVisible()
        }
        let change = state.update(distance: distance, menuHeight: menuHeight,
                                  mouseDown: NSEvent.pressedMouseButtons != 0,
                                  menuVisible: menuVisible, now: now)
        let wantFast = state.hidden || state.maskNative
            || (distance.map { $0 >= 0 && $0 <= fastZone } ?? false)
        if wantFast != fast {
            fast = wantFast
            let interval = fast ? fastInterval : slowInterval
            timer.schedule(deadline: .now() + interval, repeating: interval,
                           leeway: .milliseconds(fast ? 5 : 20))
        }
        // The native bar draws above SketchyBar, so keep it transparent while
        // the reveal delay runs. Reassert each tick: other tools reset it.
        if state.maskNative || state.maskNative != masked {
            masked = state.maskNative
            setNativeMenuAlpha(masked ? 0 : 1)
        }
        if let hidden = change {
            bar(["--bar", "hidden=\(hidden ? "on" : "off")", "y_offset=0"])
        }
    }
}
timer.resume()
RunLoop.main.run()
