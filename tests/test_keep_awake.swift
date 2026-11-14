// Rules of the keep_awake SketchyBar provider.
// swiftc sketchybar/.config/sketchybar/helpers/event_providers/keep_awake/keep_awake_logic.swift \
//   tests/test_keep_awake.swift -o /tmp/test-keep-awake && /tmp/test-keep-awake

@main
struct KeepAwakeTests {
    static func main() {
        let now = 1_000.0
        let plugged = KeepAwake(power: .ac)
        let unplugged = KeepAwake(power: .battery)

        // Automatic: awake on the adapter, off on battery.
        precondition(plugged.awake && !unplugged.awake)
        precondition(plugged.settled(power: .battery, now: now) == unplugged)
        precondition(unplugged.settled(power: .ac, now: now) == plugged)

        // A closed lid is only ignored while kept awake on the adapter.
        precondition(plugged.protectsLid && !unplugged.protectsLid)
        precondition(!plugged.turnedOff().protectsLid)
        precondition(!unplugged.keptAwake(for: nil, now: now).protectsLid)

        // A click overrides automatic until the timer ends or the power source changes.
        let timed = unplugged.keptAwake(for: 3600, now: now)
        precondition(timed.awake && timed.ends == now + 3600)
        precondition(timed.settled(power: .battery, now: now + 3599) == timed)
        precondition(timed.settled(power: .battery, now: now + 3600) == unplugged)
        precondition(timed.settled(power: .ac, now: now + 1) == plugged)
        let unlimited = unplugged.keptAwake(for: nil, now: now)
        precondition(unlimited.awake && unlimited.ends == nil)
        precondition(unlimited.settled(power: .battery, now: now + 1e9) == unlimited)
        precondition(plugged.keptAwake(for: nil, now: now).settled(power: .battery, now: now) == unplugged)

        // Turning off on the adapter lasts until it is unplugged; replugging is automatic again.
        let off = plugged.turnedOff()
        precondition(!off.awake && off.mode == .off)
        precondition(off.settled(power: .ac, now: now + 1e9) == off)
        precondition(off.settled(power: .battery, now: now).settled(power: .ac, now: now) == plugged)
        precondition(plugged.keptAwake(for: 60, now: now).turnedOff() == off)
        // On battery, off is what automatic already does.
        precondition(timed.turnedOff() == unplugged)

        let durations: [(String, Double?)] = [
            ("90", 5400), ("45m", 2700), ("2h", 7200), ("1h 30m", 5400), ("1h30", 5400),
            ("1.5h", 5400), ("1.5 hours", 5400), ("2 Hours 5 Minutes", 7500), ("1:30", 5400),
            ("0:05", 300), (" 20 min ", 1200),
            ("", nil), ("0", nil), ("0h 0m", nil), ("soon", nil), ("1:5", nil), ("-5", nil),
            ("30m 1h", nil), ("1h 2h", nil),
        ]
        for (text, expected) in durations {
            precondition(parseDuration(text) == expected,
                         "\"\(text)\": \(String(describing: parseDuration(text)))")
        }
        print("keep_awake rule checks passed")
    }
}
