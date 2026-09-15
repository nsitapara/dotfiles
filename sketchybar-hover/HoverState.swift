import Foundation

// Keep ordinary SketchyBar clicks available and debounce the return from menus.
struct HoverState {
    private(set) var hidden = false
    private var leaveTime: TimeInterval?

    mutating func update(distance: Double?, menuHeight: Int,
                         mouseDown: Bool, menuVisible: Bool, now: TimeInterval) -> Bool? {
        if !hidden {
            // Hide only once macOS reveals its menu bar, so the hand-off follows
            // the native delay instead of firing on a brush against the edge.
            if menuVisible {
                hidden = true
                leaveTime = nil
                return true
            }
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
