// Pure rules shared by the keep_awake provider and its test.

enum Power: String, Codable { case ac = "AC", battery = "BATTERY" }

/// auto follows the power source; on and off are the user's override.
enum Mode: String, Codable { case auto, on, off }

struct KeepAwake: Codable, Equatable {
    var mode = Mode.auto
    /// When a timed override ends, in seconds since 1970. Nil means no limit.
    var ends: Double?
    var power: Power

    /// Automatic keeps the Mac awake on the power adapter and lets it sleep on battery.
    var awake: Bool { mode == .on || (mode == .auto && power == .ac) }

    /// The state once the current power source and time are taken into account.
    /// Plugging in, unplugging and a timer running out all return to automatic.
    func settled(power: Power, now: Double) -> KeepAwake {
        let ended = ends.map { $0 <= now } ?? false
        if power != self.power || ended { return KeepAwake(power: power) }
        return self
    }

    func keptAwake(for seconds: Double?, now: Double) -> KeepAwake {
        KeepAwake(mode: .on, ends: seconds.map { now + $0 }, power: power)
    }

    /// On the adapter this holds until the power source changes. On battery
    /// automatic is already off.
    func turnedOff() -> KeepAwake {
        KeepAwake(mode: power == .ac ? .off : .auto, power: power)
    }
}

/// Seconds for a typed duration: "90" and "45m" are minutes, "2h", "1h 30m",
/// "1h30", "1.5 hours" and "1:30" (hours:minutes) also work. Nil when it can't
/// be read or is zero.
func parseDuration(_ text: String) -> Double? {
    let typed = text.lowercased().filter { !$0.isWhitespace }
    var hours: Substring?
    var minutes: Substring?
    if let clock = typed.wholeMatch(of: #/(\d+):(\d\d)/#) {
        (hours, minutes) = (clock.1, clock.2)
    } else if let parts = typed.wholeMatch(
        of: #/(?:(\d+(?:\.\d+)?)h[a-z]*)?(?:(\d+(?:\.\d+)?)(?:m[a-z]*)?)?/#) {
        (hours, minutes) = (parts.1, parts.2)
    } else {
        return nil
    }
    let seconds = (hours.flatMap { Double($0) } ?? 0) * 3600 + (minutes.flatMap { Double($0) } ?? 0) * 60
    return seconds > 0 ? seconds : nil
}
