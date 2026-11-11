import Foundation

// Keep ordinary SketchyBar clicks available and debounce the return from menus.
struct HoverState {
    // How long the pointer must stay at the top before the native menu bar
    // takes over from SketchyBar.
    static let revealDelay: TimeInterval = 3
    // After the pointer leaves the top, the native bar takes about half a
    // second to slide away. Don't mistake that for a keyboard-opened menu.
    static let retractGrace: TimeInterval = 1

    private(set) var hidden = false
    // Whether the native menu bar should be kept transparent right now.
    private(set) var maskNative = false
    private var leaveTime: TimeInterval?
    private var hoverStart: TimeInterval?
    private var lastInZone: TimeInterval?

    mutating func update(distance: Double?, menuHeight: Int,
                         mouseDown: Bool, menuVisible: Bool, now: TimeInterval) -> Bool? {
        if !hidden {
            let inZone = distance.map { $0 >= 0 && $0 <= Double(menuHeight) } ?? false
            if inZone {
                if hoverStart == nil { hoverStart = now }
                lastInZone = now
            } else {
                hoverStart = nil
            }
            let holding = hoverStart.map { now - $0 < Self.revealDelay } ?? false
            let retracting = !inZone && (lastInZone.map { now - $0 < Self.retractGrace } ?? false)
            maskNative = holding || (retracting && menuVisible)
            // Hide only once macOS reveals its menu bar, so brushing the edge
            // does nothing. A pointer reveal waits out revealDelay; a keyboard
            // reveal (pointer away from the top) hands off at once.
            guard menuVisible, !holding, !retracting else { return nil }
            hidden = true
            maskNative = false
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
