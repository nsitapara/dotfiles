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
        let delay = HoverState.revealDelay
        precondition(update(100, 0) == nil)
        precondition(update(20, 0.1) == nil) // Ordinary bar interaction stays put.
        precondition(update(1, 0.2, down: true) == nil) // Dragging to the top.
        precondition(update(1, 0.3) == nil) // Brushing the edge alone does nothing.
        precondition(update(1, 0.6, menu: true) == nil) // Native bar out: hold SketchyBar.
        precondition(update(1, 0.1 + delay - 0.05, menu: true) == nil && !state.hidden)
        precondition(update(1, 0.1 + delay + 0.01, menu: true) == true) // Hand off after the delay.
        precondition(update(30, 3.4) == nil && state.hidden)
        precondition(update(100, 3.5) == nil)
        precondition(update(30, 3.6) == nil) // Returning cancels the leave delay.
        precondition(update(100, 3.7) == nil)
        precondition(update(100, 3.9) == nil && state.hidden)
        precondition(update(100, 4.1) == false)

        // Leaving the top zone restarts the delay.
        precondition(update(0, 5, menu: true) == nil)
        precondition(update(100, 6) == nil)
        precondition(update(0, 6.5, menu: true) == nil)
        precondition(update(0, 5 + delay + 0.1, menu: true) == nil && !state.hidden)
        precondition(update(0, 6.5 + delay, menu: true) == true)
        precondition(update(nil, 10.1) == nil) // Leaving all displays restores it.
        precondition(update(nil, 10.5) == false)

        // Keyboard/menu-item activation (pointer away from the top) hides at once.
        precondition(update(400, 11, menu: true) == true)
        precondition(update(150, 11.1, down: true) == nil)
        precondition(update(150, 11.6, down: true) == nil && state.hidden)
        precondition(update(400, 12, menu: true) == nil) // Dropdown below the bar.
        precondition(update(400, 13, menu: true) == nil && state.hidden)
        precondition(update(400, 13.1) == nil)
        precondition(update(400, 13.5) == false)
        print("SketchyBar hover state checks passed")
    }
}
