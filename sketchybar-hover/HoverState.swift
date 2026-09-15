import Foundation

// Separate enter/leave thresholds keep the moving bar from chasing the pointer.
struct HoverState {
    private(set) var offset = 0
    private var leaveTime: TimeInterval?

    mutating func update(distance: Double?, menuHeight: Int, barHeight: Int,
                         mouseDown: Bool, now: TimeInterval) -> Int? {
        if offset == 0 {
            if let distance, distance >= 0, distance <= 2, !mouseDown {
                offset = menuHeight
                leaveTime = nil
                return offset
            }
        } else if let distance, distance >= 0,
                  distance <= Double(offset + barHeight + 8) {
            leaveTime = nil
        } else if mouseDown {
            leaveTime = nil
        } else if let start = leaveTime {
            if now - start >= 0.35 {
                offset = 0
                leaveTime = nil
                return 0
            }
        } else {
            leaveTime = now
        }
        return nil
    }
}
