import Foundation

@main
struct HoverTests {
    static func main() {
        var state = HoverState()
        func update(_ distance: Double?, _ now: Double, down: Bool = false) -> Int? {
            state.update(distance: distance, menuHeight: 36, barHeight: 40,
                         mouseDown: down, now: now)
        }
        precondition(update(20, 0) == nil) // Ordinary bar interaction stays put.
        precondition(update(1, 0.1, down: true) == nil) // Dragging to the top.
        precondition(update(1, 0.2) == 36)
        precondition(update(60, 0.3) == nil && state.offset == 36)
        precondition(update(100, 0.4) == nil)
        precondition(update(60, 0.5) == nil) // Returning cancels the leave delay.
        precondition(update(100, 0.6) == nil)
        precondition(update(100, 0.8) == nil && state.offset == 36)
        precondition(update(100, 1.0) == 0)
        precondition(update(-1, 1.1) == nil)
        precondition(update(0, 1.2) == 36)
        precondition(update(nil, 1.3) == nil) // Leaving all displays restores it.
        precondition(update(nil, 1.7) == 0)
        precondition(update(0, 2) == 36)
        precondition(update(150, 2.1, down: true) == nil)
        precondition(update(150, 2.6, down: true) == nil && state.offset == 36)
        print("SketchyBar hover state checks passed")
    }
}
