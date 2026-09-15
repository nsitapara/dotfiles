import AppKit
import ApplicationServices

// A short-lived, separately permissioned app. Only presses Mission Control's
// Add Desktop buttons; never closes desktops or moves existing windows.
struct Failure: Error, CustomStringConvertible { let description: String }
struct Space: Decodable {
    let display: Int
    let label: String
    let fullscreen: Bool
    enum CodingKeys: String, CodingKey {
        case display, label
        case fullscreen = "is-native-fullscreen"
    }
}
struct Display: Decodable { let id: Int; let index: Int }
struct DisplayPlan: Decodable { let id: Int; let index: Int; let workspaces: [Int] }

func run(_ executable: String, _ arguments: [String]) throws -> Data {
    let task = Process(), pipe = Pipe()
    task.executableURL = URL(fileURLWithPath: executable)
    task.arguments = arguments
    task.standardOutput = pipe
    task.standardError = FileHandle.nullDevice
    try task.run()
    let result = pipe.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    guard task.terminationStatus == 0 else { throw Failure(description: "Command failed: \(executable)") }
    return result
}
func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var result: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &result) == .success else { return nil }
    return result
}
func children(_ element: AXUIElement) -> [AXUIElement] {
    attribute(element, "AXChildren") as? [AXUIElement] ?? []
}
func child(_ element: AXUIElement, _ identifier: String) -> AXUIElement? {
    children(element).first { attribute($0, "AXIdentifier") as? String == identifier }
}
func waitFor<T>(_ action: () throws -> T?) rethrows -> T? {
    let deadline = Date().addingTimeInterval(4)
    repeat {
        if let result = try action() { return result }
        Thread.sleep(forTimeInterval: 0.1)
    } while Date() < deadline
    return nil
}
func ensureSpaces(yabai: String, plan: [DisplayPlan]) throws -> Int {
    func displays() throws -> [Display] {
        try JSONDecoder().decode([Display].self, from: run(yabai, ["-m", "query", "--displays"]))
    }
    func spaces() throws -> [Space] {
        try JSONDecoder().decode([Space].self, from: run(yabai, ["-m", "query", "--spaces"]))
    }
    func count(_ all: [Space], _ display: Display) -> Int {
        all.filter {
            $0.display == display.index && !$0.fullscreen &&
            ($0.label.isEmpty || $0.label.range(of: "^ws[1-9]$", options: .regularExpression) != nil)
        }.count
    }
    let screens = try displays()
    guard !plan.isEmpty, plan.count <= 3,
          plan.map(\.id).sorted() == screens.map(\.id).sorted(),
          plan.allSatisfy({ entry in
              screens.contains { $0.id == entry.id && $0.index == entry.index } &&
              (1...6).contains(entry.workspaces.count)
          }) else { throw Failure(description: "Monitor layout changed; retry after it settles.") }
    let initial = try spaces()
    guard screens.contains(where: { screen in
        count(initial, screen) < plan.first(where: { $0.id == screen.id })!.workspaces.count
    }) else { return 0 }
    // Display events and periodic checks must never open permission dialogs.
    // Opening this app explicitly from Finder still requests access below.
    guard AXIsProcessTrusted() else {
        throw Failure(description: "Enable Dotfiles Spaces in System Settings > Privacy & Security > Accessibility, then run ./wm.sh spaces again.")
    }
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first else {
        throw Failure(description: "Dock is not running.")
    }
    let dock = AXUIElementCreateApplication(app.processIdentifier)
    AXUIElementSetMessagingTimeout(dock, 2)
    let wasOpen = child(dock, "mc") != nil
    if !wasOpen { _ = try run("/usr/bin/open", ["-a", "Mission Control"]) }
    defer {
        if !wasOpen && child(dock, "mc") != nil {
            // Opening Mission Control a second time toggles it closed.
            _ = try? run("/usr/bin/open", ["-a", "Mission Control"])
        }
    }
    guard waitFor({ child(dock, "mc") }) != nil else {
        throw Failure(description: "Mission Control did not expose its Accessibility controls.")
    }
    var created = 0
    for screen in screens {
        let target = plan.first(where: { $0.id == screen.id })!.workspaces.count
        // Requery after each click: native indices can change as Spaces appear.
        for _ in 0..<target {
            guard try displays().map(\.id) == screens.map(\.id) else {
                throw Failure(description: "Monitors changed during setup; retry once they settle.")
            }
            let before = try count(spaces(), screen)
            if before >= target { break }
            let add: AXUIElement? = waitFor {
                guard let mc = child(dock, "mc"),
                      let display = children(mc).first(where: {
                          attribute($0, "AXIdentifier") as? String == "mc.display" &&
                          (attribute($0, "AXDisplayID") as? NSNumber)?.intValue == screen.id
                      }), let group = child(display, "mc.spaces") else { return nil }
                return child(group, "mc.spaces.add")
            }
            guard let button = add,
                  AXUIElementPerformAction(button, kAXPressAction as CFString) == .success else {
                throw Failure(description: "Could not press Add Desktop on display \(screen.index).")
            }
            guard try waitFor({ try count(spaces(), screen) > before ? true : nil }) != nil else {
                throw Failure(description: "macOS did not create the desktop; stopped to avoid repeated clicks.")
            }
            created += 1
        }
    }
    return created
}

let arguments = CommandLine.arguments
if arguments.count == 2 && arguments[1] == "--display-info" {
    // Read-only metadata for per-screen notch padding; no Accessibility needed.
    var ids = [CGDirectDisplayID](repeating: 0, count: 16)
    var count: UInt32 = 0
    guard CGGetActiveDisplayList(16, &ids, &count) == .success else { exit(1) }
    let result = ids.prefix(Int(count)).map { id -> [String: Any] in
        let screen = NSScreen.screens.first {
            ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == id
        }
        let frame = CGDisplayBounds(id)
        let uuid = CGDisplayCreateUUIDFromDisplayID(id).takeRetainedValue()
        return ["id": Int(id), "builtin": CGDisplayIsBuiltin(id) != 0,
                "name": screen?.localizedName ?? "", "uuid": CFUUIDCreateString(nil, uuid) as String,
                "frame": ["x":frame.origin.x, "y":frame.origin.y, "w":frame.width, "h":frame.height]]
    }
    if let data = try? JSONSerialization.data(withJSONObject: result),
       let json = String(data: data, encoding: .utf8) { print(json) }
} else if arguments.count == 4 {
    let resultPath = arguments[2]
    let message: String
    do {
        let plan = try JSONDecoder().decode([DisplayPlan].self, from: Data(contentsOf: URL(fileURLWithPath: arguments[3])))
        message = "OK Created \(try ensureSpaces(yabai: arguments[1], plan: plan)) missing desktops.\n"
    }
    catch { message = "ERROR \(error)\n" }
    try? message.write(toFile: resultPath, atomically: true, encoding: .utf8)
} else {
    // Opening the app from Finder is also a way to request its own permission.
    let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    _ = AXIsProcessTrustedWithOptions(options)
}
