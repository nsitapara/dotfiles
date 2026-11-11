// Pure formatting shared by the ai_usage provider and its test.

let week: Double = 7 * 24 * 3600

struct UsageWindow {
    let used: Double?
    let seconds: Double?
}

/// The tightest limit as "82%", marked "W 82%" when it is the weekly one of
/// two windows (how CodexBar labels it). Nil when no window has a reading.
func formatUsage(_ windows: [UsageWindow]) -> String? {
    let readings = windows.compactMap { window in
        window.used.map { (used: $0, seconds: window.seconds) }
    }
    // max(by:) keeps the first of equal readings, so a tie shows the primary one.
    guard let shown = readings.indices.max(by: { readings[$0].used < readings[$1].used })
    else { return nil }
    let named = readings.count > 1 && shown != 0 && readings[shown].seconds == week
    return (named ? "W " : "") + String(Int(readings[shown].used.rounded())) + "%"
}
