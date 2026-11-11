// Formatting of the ai_usage SketchyBar provider.
// swiftc sketchybar/.config/sketchybar/helpers/event_providers/ai_usage/usage_format.swift \
//   tests/test_ai_usage.swift -o /tmp/test-ai-usage && /tmp/test-ai-usage

@main
struct AIUsageTests {
    static func main() {
        let hour = 3600.0
        let cases: [([UsageWindow], String?)] = [
            // Claude: no active 5-hour session, weekly window only.
            ([UsageWindow(used: nil, seconds: 5 * hour), UsageWindow(used: 82, seconds: week)], "82%"),
            // The 5-hour window is tighter: show it unmarked.
            ([UsageWindow(used: 40, seconds: 5 * hour), UsageWindow(used: 12, seconds: week)], "40%"),
            // The weekly one of two windows is tighter: mark it.
            ([UsageWindow(used: 4, seconds: 5 * hour), UsageWindow(used: 82.4, seconds: week)], "W 82%"),
            // Codex: a single weekly primary window is not marked.
            ([UsageWindow(used: 6, seconds: week), UsageWindow(used: nil, seconds: nil)], "6%"),
            // A tie shows the primary window.
            ([UsageWindow(used: 30, seconds: 5 * hour), UsageWindow(used: 30, seconds: week)], "30%"),
            ([UsageWindow(used: 99.6, seconds: 5 * hour)], "100%"),
            ([UsageWindow(used: nil, seconds: week)], nil),
            ([], nil),
        ]
        for (index, (windows, expected)) in cases.enumerated() {
            precondition(formatUsage(windows) == expected, "case \(index): \(String(describing: formatUsage(windows)))")
        }
        print("ai_usage formatting checks passed")
    }
}
