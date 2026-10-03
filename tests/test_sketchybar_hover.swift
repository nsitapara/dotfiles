import Foundation

@main
struct HoverTests {
    static func main() {
        var state = HoverState()
        func update(_ distance: Double?, _ now: Double, down: Bool = false,
                    menu: Bool = false) -> Bool? {
            state.update(distance: distance, menuHeight: 36,
                         mouseDown: down, menuVisible: menu, now: now)
        }
        precondition(update(20, 0) == nil) // Ordinary bar interaction stays put.
        precondition(update(1, 0.1, down: true) == nil) // Dragging to the top.
        precondition(update(1, 0.2) == nil) // Brushing the edge alone does nothing.
        precondition(update(1, 0.3, menu: true) == true) // Hide as the native bar appears.
        precondition(update(30, 0.4) == nil && state.hidden)
        precondition(update(100, 0.5) == nil)
        precondition(update(30, 0.6) == nil) // Returning cancels the leave delay.
        precondition(update(100, 0.7) == nil)
        precondition(update(100, 0.9) == nil && state.hidden)
        precondition(update(100, 1.1) == false)
        precondition(update(-1, 1.15) == nil)
        precondition(update(0, 1.2, menu: true) == true)
        precondition(update(nil, 1.3) == nil) // Leaving all displays restores it.
        precondition(update(nil, 1.7) == false)
        precondition(update(0, 2, menu: true) == true)
        precondition(update(150, 2.1, down: true) == nil)
        precondition(update(150, 2.6, down: true) == nil && state.hidden)
        precondition(update(400, 3, menu: true) == nil) // Dropdown below the bar.
        precondition(update(400, 4, menu: true) == nil && state.hidden)
        precondition(update(400, 4.1) == nil)
        precondition(update(400, 4.5) == false)
        precondition(update(400, 5, menu: true) == true) // Keyboard/menu-item activation.
        print("SketchyBar hover state checks passed")
    }
}
