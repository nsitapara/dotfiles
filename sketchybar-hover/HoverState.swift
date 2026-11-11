import Foundation

// Keep ordinary SketchyBar clicks available and debounce the return from menus.
struct HoverState {
    // How long the pointer must stay at the top before the native menu bar
    // takes over from SketchyBar.
    static let revealDelay: TimeInterval = 3

    private(set) var hidden = false
    private var leaveTime: TimeInterval?
    private var hoverStart: TimeInterval?

    mutating func update(distance: Double?, menuHeight: Int,
                         mouseDown: Bool, menuVisible: Bool, now: TimeInterval) -> Bool? {
        if !hidden {
            let inMenuZone = distance.map { $0 >= 0 && $0 <= Double(menuHeight) } ?? false
            if !inMenuZone {
                hoverStart = nil
            } else if hoverStart == nil {
                hoverStart = now
            }
            // Hide only once macOS reveals its menu bar, so brushing the edge
            // does nothing. A pointer reveal waits out revealDelay from when the
            // pointer reached the top; a keyboard reveal (pointer elsewhere)
            // hands off at once.
            guard menuVisible else { return nil }
            if let start = hoverStart, now - start < Self.revealDelay { return nil }
            hidden = true
            leaveTime = nil
            hoverStart = nil
            return true
        } else if menuVisible {
            leaveTime = nil
        } else if let distance, distance >= 0,
                  distance <= Double(menuHeight + 8) {
            leaveTime = nil
        } else if mouseDown {
            leaveTime = nil
        } else if let start = leaveTime {
            if now - start >= 0.35 {
                hidden = false
                leaveTime = nil
                return false
            }
        } else {
            leaveTime = now
        }
        return nil
    }
}
