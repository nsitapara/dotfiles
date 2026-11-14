// Keeps the Mac awake for the bar's coffee-cup widget, without the Amphetamine
// app. While the rules in keep_awake_logic.swift say "awake", the provider holds
// one power assertion against idle sleep (display sleep stays allowed) and, on
// the power adapter, also stops a closed lid from sleeping the Mac. It fires one
// SketchyBar event whenever that changes:
//   <event> awake=1 mode=auto power=AC ends=0 lid=1
//
// Usage:
//   keep_awake daemon <event-name>     the provider; runs until the bar replaces it
//   keep_awake set auto|off|on [secs]  the widget's menu; "on" without seconds has no limit
//   keep_awake custom                  ask for a duration, then "set on" with it
//   keep_awake sync [AC|BATTERY]       re-check the power source (an argument pretends, for testing;
//                                      it leaves the lid setting alone)
//   keep_awake status                  the event's fields as JSON
import Foundation
import IOKit.ps
import IOKit.pwr_mgt
import notify

let stateDirectory = NSHomeDirectory() + "/.local/state/sketchybar"
let stateFile = stateDirectory + "/keep-awake.json"
let syncNotification = "dotfiles.sketchybar.keep_awake.sync"
let sketchybar = "/opt/homebrew/bin/sketchybar"
// SbarLua puts a 60-second alarm on exec children; the provider runs forever
// and the duration dialog can stay open longer than that.
alarm(0)

@discardableResult
func run(_ path: String, _ arguments: [String]) -> String? {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: path)
    task.arguments = arguments
    let output = Pipe()
    task.standardOutput = output
    task.standardError = FileHandle.nullDevice
    guard (try? task.run()) != nil else { return nil }
    let data = output.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    return task.terminationStatus == 0 ? String(decoding: data, as: UTF8.self) : nil
}

func currentPower() -> Power {
    let sources = IOPSCopyPowerSourcesInfo().takeRetainedValue()
    let providing = IOPSGetProvidingPowerSourceType(sources).takeUnretainedValue() as String
    return providing == kIOPSBatteryPowerValue ? .battery : .ac
}

/// The power manager's IORegistry entry; the caller releases it.
func powerManager() -> io_service_t {
    IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOPMrootDomain"))
}

func lidIsClosed() -> Bool {
    let root = powerManager()
    defer { IOObjectRelease(root) }
    let closed = IORegistryEntryCreateCFProperty(root, "AppleClamshellState" as CFString, kCFAllocatorDefault, 0)
    return (closed?.takeRetainedValue() as? Bool) ?? false
}

/// Tells the kernel whether a closed lid may put the Mac to sleep. An idle-sleep
/// assertion does not cover this: without it a docked, closed Mac sleeps as soon
/// as its displays do. It is the call powerd itself makes (and Amphetamine made),
/// kPMSetClamshellSleepState, and the setting outlives this connection.
/// Allowing sleep again while the lid is closed sleeps the Mac at once.
@discardableResult
func setLidSleep(disabled: Bool) -> Bool {
    let root = powerManager()
    defer { IOObjectRelease(root) }
    var connection: io_connect_t = 0
    guard IOServiceOpen(root, mach_task_self_, 0, &connection) == KERN_SUCCESS else {
        fputs("keep_awake: cannot reach the power manager\n", stderr)
        return false
    }
    defer { IOServiceClose(connection) }
    let setClamshellSleepState: UInt32 = 12
    var input: UInt64 = disabled ? 1 : 0
    let result = IOConnectCallScalarMethod(connection, setClamshellSleepState, &input, 1, nil, nil)
    if result != KERN_SUCCESS { fputs("keep_awake: lid sleep setting refused (\(result))\n", stderr) }
    return result == KERN_SUCCESS
}

/// Holds an exclusive lock on a file in the state directory until the returned
/// descriptor is closed or the process exits.
func lock(_ name: String) -> Int32 {
    try? FileManager.default.createDirectory(atPath: stateDirectory, withIntermediateDirectories: true)
    let descriptor = open(stateDirectory + "/" + name, O_CREAT | O_RDWR, 0o600)
    flock(descriptor, LOCK_EX)
    return descriptor
}

/// The saved state settled for `power` and the time now. The file also carries
/// the override and the last power source across bar reloads and profile
/// switches, so a change that happened while no provider ran is still seen.
func settledState(power: Power) -> (saved: KeepAwake?, now: Double, state: KeepAwake) {
    let now = Date().timeIntervalSince1970
    let saved = FileManager.default.contents(atPath: stateFile)
        .flatMap { try? JSONDecoder().decode(KeepAwake.self, from: $0) }
    return (saved, now, (saved ?? KeepAwake(power: power)).settled(power: power, now: now))
}

@discardableResult
func update(power: Power, _ change: (KeepAwake, Double) -> KeepAwake = { state, _ in state }) -> KeepAwake {
    let descriptor = lock("keep-awake.json.lock")
    defer { close(descriptor) }
    let (saved, now, settled) = settledState(power: power)
    let state = change(settled, now)
    if state != saved, let data = try? JSONEncoder().encode(state) {
        try? data.write(to: URL(fileURLWithPath: stateFile), options: .atomic)
    }
    return state
}

/// Asks the running provider to re-check. `pretend` makes it act as if that
/// power source were connected. Not named sync: a bare sync() call is libc's.
func requestSync(pretend: Power? = nil) {
    var token: Int32 = 0
    notify_register_check(syncNotification, &token)
    let codes: [Power?: UInt64] = [nil: 0, .ac: 1, .battery: 2]
    notify_set_state(token, codes[pretend] ?? 0)
    notify_post(syncNotification)
}

func fields(_ state: KeepAwake) -> [(String, String)] {
    [("awake", state.awake ? "1" : "0"), ("mode", state.mode.rawValue),
     ("power", state.power.rawValue), ("ends", String(Int(state.ends ?? 0))),
     ("lid", lidIsClosed() ? "1" : "0")]
}

func runDaemon(event: String) -> Never {
    // The newest bar's provider takes over; wait for the one it replaced to exit.
    _ = lock("keep-awake.daemon.lock")
    run(sketchybar, ["--add", "event", event])
    var assertion = IOPMAssertionID(kIOPMNullAssertionID)
    var timer: DispatchSourceTimer?
    // Present while this provider has told the kernel to ignore a closed lid, so
    // only a setting it made is ever undone, also after a bar reload.
    let lidMarker = stateDirectory + "/keep-awake.lid"

    func apply(pretend: Power? = nil) {
        let state = update(power: pretend ?? currentPower())
        // A pretended power source must never really sleep a closed Mac.
        if pretend != nil {
        } else if state.protectsLid {
            if setLidSleep(disabled: true) { FileManager.default.createFile(atPath: lidMarker, contents: nil) }
        } else if FileManager.default.fileExists(atPath: lidMarker) {
            setLidSleep(disabled: false)
            try? FileManager.default.removeItem(atPath: lidMarker)
        }
        if state.awake, assertion == kIOPMNullAssertionID {
            IOPMAssertionCreateWithName(kIOPMAssertPreventUserIdleSystemSleep as CFString,
                                        IOPMAssertionLevel(kIOPMAssertionLevelOn),
                                        "SketchyBar keep awake" as CFString,
                                        &assertion)
        } else if !state.awake, assertion != kIOPMNullAssertionID {
            IOPMAssertionRelease(assertion)
            assertion = IOPMAssertionID(kIOPMNullAssertionID)
        }
        timer?.cancel()
        timer = nil
        if let ends = state.ends {
            // Wall-clock time, so a timer that ran out during sleep fires on wake.
            let source = DispatchSource.makeTimerSource(queue: .main)
            source.schedule(wallDeadline: .now() + max(ends - Date().timeIntervalSince1970, 0) + 0.1)
            source.setEventHandler { apply() }
            source.resume()
            timer = source
        }
        run(sketchybar, ["--trigger", event] + fields(state).map { $0 + "=" + $1 })
    }

    var syncToken: Int32 = 0
    notify_register_dispatch(syncNotification, &syncToken, .main) { token in
        var code: UInt64 = 0
        notify_get_state(token, &code)
        let pretended: [UInt64: Power] = [1: .ac, 2: .battery]
        apply(pretend: pretended[code])
    }
    // macOS posts this when the adapter is plugged in or pulled, so the rule
    // holds even while no bar is running to forward its own power event.
    var powerToken: Int32 = 0
    notify_register_dispatch(kIOPSNotifyPowerSource, &powerToken, .main) { _ in apply() }
    // powerd shares the lid setting and rewrites it around wake and display
    // changes, and the kernel acts on it about 30 seconds after a wake.
    let lidGuard = DispatchSource.makeTimerSource(queue: .main)
    lidGuard.schedule(deadline: .now() + 20, repeating: 20)
    lidGuard.setEventHandler {
        if FileManager.default.fileExists(atPath: lidMarker) { setLidSleep(disabled: true) }
    }
    lidGuard.resume()
    apply()
    dispatchMain()
}

/// A typed duration from a dialog, or nil when it is cancelled.
func askDuration() -> Double? {
    var prompt = "Keep awake for how long?\n\nMinutes, or a time such as 45m, 1h 30m or 1:30."
    while true {
        guard let typed = run("/usr/bin/osascript", [
            "-e", "on run arguments",
            "-e", "tell current application to activate",
            "-e", "text returned of (display dialog (item 1 of arguments) default answer \"1h\" "
                + "with title \"Keep awake\" buttons {\"Cancel\", \"Start\"} default button \"Start\")",
            "-e", "end run", "--", prompt,
        ]) else { return nil }
        if let seconds = parseDuration(typed) { return seconds }
        prompt = "That time could not be read.\n\nType minutes, or a time such as 45m, 1h 30m or 1:30."
    }
}

func usage() -> Never {
    fputs("Usage: keep_awake daemon <event-name> | set auto|off|on [seconds] | custom | sync [AC|BATTERY] | status\n",
          stderr)
    exit(1)
}

func keepAwake(for seconds: Double?) {
    update(power: currentPower()) { state, now in state.keptAwake(for: seconds, now: now) }
    requestSync()
}

let arguments = Array(CommandLine.arguments.dropFirst())
switch (arguments.first, arguments.count) {
case ("daemon", 2):
    runDaemon(event: arguments[1])
case ("set", 2) where arguments[1] == "auto":
    update(power: currentPower()) { state, _ in KeepAwake(power: state.power) }
    requestSync()
case ("set", 2) where arguments[1] == "off":
    update(power: currentPower()) { state, _ in state.turnedOff() }
    requestSync()
case ("set", 2) where arguments[1] == "on":
    keepAwake(for: nil)
case ("set", 3) where arguments[1] == "on":
    guard let seconds = Double(arguments[2]), seconds > 0 else { usage() }
    keepAwake(for: seconds)
case ("custom", 1):
    if let seconds = askDuration() { keepAwake(for: seconds) }
case ("sync", 1):
    requestSync()
case ("sync", 2):
    guard let power = Power(rawValue: arguments[1]) else { usage() }
    requestSync(pretend: power)
case ("status", 1):
    let state = settledState(power: currentPower()).state
    let json = fields(state).map { name, value in
        "\"\(name)\":" + (Int(value) == nil ? "\"\(value)\"" : value)
    }
    print("{" + json.joined(separator: ",") + "}")
default:
    usage()
}
