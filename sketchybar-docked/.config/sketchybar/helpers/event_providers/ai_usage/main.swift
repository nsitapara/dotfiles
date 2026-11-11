// Claude and Codex plan usage for the bar, without the CodexBar app or CLI.
// Every <seconds> it asks each service's usage endpoint directly, using the
// login token its own CLI already stores, and fires one SketchyBar event:
//   <event> claude='W 82%' codex='6%'
// A provider that fails is left out, so the bar keeps its last reading.
//
// Usage: ai_usage <event-name> <seconds>
// Both endpoints are undocumented. Anthropic's answers HTTP 429 when polled
// more often than about every 5 minutes; Retry-After is honoured.
import Foundation

let args = CommandLine.arguments
guard args.count == 3, let interval = Double(args[2]), interval >= 60 else {
    fputs("Usage: ai_usage <event-name> <seconds (>= 60)>\n", stderr)
    exit(1)
}
let event = args[1]
// SbarLua puts a 60-second alarm on exec children; this one runs forever.
alarm(0)

@discardableResult
func run(_ path: String, _ arguments: [String]) -> Data? {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: path)
    task.arguments = arguments
    let output = Pipe()
    task.standardOutput = output
    task.standardError = FileHandle.nullDevice
    guard (try? task.run()) != nil else { return nil }
    let data = output.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    return task.terminationStatus == 0 ? data : nil
}

func object(_ data: Data?) -> [String: Any]? {
    data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
}

let session: URLSession = {
    let configuration = URLSessionConfiguration.ephemeral
    configuration.timeoutIntervalForRequest = 15
    return URLSession(configuration: configuration)
}()

enum FetchError: Error { case unavailable, rateLimited(TimeInterval) }

func fetch(_ url: String, _ headers: [String: String]) async throws -> [String: Any] {
    var request = URLRequest(url: URL(string: url)!)
    for (field, value) in headers { request.setValue(value, forHTTPHeaderField: field) }
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    request.setValue("dotfiles-ai-usage", forHTTPHeaderField: "User-Agent")
    let (data, response) = try await session.data(for: request)
    let status = (response as? HTTPURLResponse)?.statusCode ?? 0
    if status == 429 {
        let retry = (response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Retry-After")
        throw FetchError.rateLimited(max(Double(retry ?? "") ?? 0, interval))
    }
    guard status == 200, let body = object(data) else { throw FetchError.unavailable }
    return body
}

// Claude Code keeps its OAuth login in this keychain item and refreshes it while
// you use it. Reading it through /usr/bin/security reuses that tool's existing
// keychain access instead of prompting for this binary after every rebuild.
func claudeUsage() async throws -> String? {
    let item = object(run("/usr/bin/security",
                          ["find-generic-password", "-s", "Claude Code-credentials", "-w"]))
    guard let oauth = item?["claudeAiOauth"] as? [String: Any],
          let token = oauth["accessToken"] as? String else { throw FetchError.unavailable }
    let usage = try await fetch("https://api.anthropic.com/api/oauth/usage", [
        "Authorization": "Bearer " + token,
        "anthropic-beta": "oauth-2025-04-20",
    ])
    let windows = [("five_hour", 5 * 3600.0), ("seven_day", week)].compactMap { key, seconds in
        (usage[key] as? [String: Any]).map {
            UsageWindow(used: ($0["utilization"] as? NSNumber)?.doubleValue, seconds: seconds)
        }
    }
    return formatUsage(windows)
}

// Codex keeps its ChatGPT login here and refreshes it while you use it.
func codexUsage() async throws -> String? {
    let path = NSHomeDirectory() + "/.codex/auth.json"
    guard let tokens = object(FileManager.default.contents(atPath: path))?["tokens"] as? [String: Any],
          let token = tokens["access_token"] as? String else { throw FetchError.unavailable }
    let usage = try await fetch("https://chatgpt.com/backend-api/wham/usage", [
        "Authorization": "Bearer " + token,
        "ChatGPT-Account-Id": tokens["account_id"] as? String ?? "",
    ])
    let limits = usage["rate_limit"] as? [String: Any] ?? [:]
    let windows = ["primary_window", "secondary_window"].compactMap { key in
        (limits[key] as? [String: Any]).map {
            UsageWindow(used: ($0["used_percent"] as? NSNumber)?.doubleValue,
                        seconds: ($0["limit_window_seconds"] as? NSNumber)?.doubleValue)
        }
    }
    return formatUsage(windows)
}

run("/opt/homebrew/bin/sketchybar", ["--add", "event", event])
var claudeNotBefore = Date.distantPast
while true {
    var fields: [String] = []
    if Date() >= claudeNotBefore {
        do {
            if let text = try await claudeUsage() { fields.append("claude=" + text) }
        } catch FetchError.rateLimited(let seconds) {
            claudeNotBefore = Date().addingTimeInterval(seconds)
        } catch {}
    }
    if let text = try? await codexUsage() { fields.append("codex=" + text) }
    if !fields.isEmpty {
        run("/opt/homebrew/bin/sketchybar", ["--trigger", event] + fields)
    }
    try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
}
