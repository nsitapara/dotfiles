import AppKit
import Darwin

// Pointer polling requires neither Accessibility nor Input Monitoring access.
// See https://github.com/malpern/sketchybar-toggle for the hide/show alternative.
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
    bar(["--bar", "topmost=off", "y_offset=0"])
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
bar(["--bar", "topmost=window", "y_offset=0"])
let timer = DispatchSource.makeTimerSource(queue: .main)
timer.schedule(deadline: .now(), repeating: .milliseconds(33), leeway: .milliseconds(5))
timer.setEventHandler {
    autoreleasepool {
        ticks += 1
        if ticks % 30 == 0 && kill(barPID, 0) != 0 { exit(0) }
        let pointer = NSEvent.mouseLocation
        let screen = NSScreen.screens.first {
            $0.frame.insetBy(dx: -1, dy: -1).contains(pointer)
        }
        let distance = screen.map { Double($0.frame.maxY - pointer.y) }
        // Auto-hide can report a zero visible-frame inset. Reserve at least 36pt
        // for the native menu, including its background, or the notch's safe area.
        let menuHeight = Int(ceil(max(36, screen?.safeAreaInsets.top ?? 0)))
        if let offset = state.update(distance: distance, menuHeight: menuHeight,
                                     barHeight: 40,
                                     mouseDown: NSEvent.pressedMouseButtons != 0,
                                     now: ProcessInfo.processInfo.systemUptime) {
            bar(["--animate", "sin", "10", "--bar", "y_offset=\(offset)"])
        }
    }
}
timer.resume()
RunLoop.main.run()
