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

func restore() {
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
var ticks = 0
var menuVisible = false
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
bar(["--bar", "topmost=window", "hidden=off", "y_offset=0"])
let timer = DispatchSource.makeTimerSource(queue: .main)
timer.schedule(deadline: .now(), repeating: .milliseconds(33), leeway: .milliseconds(5))
timer.setEventHandler {
    autoreleasepool {
        ticks += 1
        if ticks % 30 == 0 {
            if kill(barPID, 0) != 0 { exit(0) }
            refreshScreens()
        }
        let pointer = NSEvent.mouseLocation
        let screen = screens.first { $0.frame.insetBy(dx: -1, dy: -1).contains(pointer) }
        let distance = screen.map { Double($0.frame.maxY - pointer.y) }
        let menuHeight = screen?.menuHeight ?? 36
        // The window-list query is the costly part. Poll it at 30 Hz only while
        // the pointer is in the menu zone so the hide lands as the bar appears,
        // 10 Hz while hidden to notice the menu closing, and 2 Hz otherwise for
        // keyboard-driven menu activation.
        let nearTop = distance.map { $0 >= 0 && $0 <= Double(menuHeight) } ?? false
        let menuInterval = nearTop ? 1 : (state.hidden ? 3 : 15)
        if ticks % menuInterval == 0 { menuVisible = nativeMenuVisible() }
        if let hidden = state.update(distance: distance, menuHeight: menuHeight,
                                     mouseDown: NSEvent.pressedMouseButtons != 0,
                                     menuVisible: menuVisible,
                                     now: ProcessInfo.processInfo.systemUptime) {
            bar(["--bar", "hidden=\(hidden ? "on" : "off")", "y_offset=0"])
        }
    }
}
timer.resume()
RunLoop.main.run()
