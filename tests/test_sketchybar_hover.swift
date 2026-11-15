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
        precondition(update(100, 0) == nil && !state.maskNative)
        precondition(update(20, 0.1) == nil) // Ordinary bar interaction stays put.
        precondition(state.maskNative) // Native bar kept invisible from the start.
        precondition(update(1, 0.2, down: true) == nil) // Dragging to the top.
        precondition(update(1, 0.3) == nil) // Brushing the edge alone does nothing.
        precondition(update(1, 0.6, menu: true) == nil) // Native bar out: hold SketchyBar.
        precondition(update(1, 0.3 + delay - 0.05, menu: true) == nil)
        precondition(!state.hidden && state.maskNative)
        precondition(update(1, 0.3 + delay + 0.01, menu: true) == true) // Hand off after the delay.
        precondition(!state.maskNative) // Native bar shown once SketchyBar hides.
        precondition(update(30, 3.4) == nil && state.hidden)
        precondition(update(100, 3.5) == nil)
        precondition(update(30, 3.6) == nil) // Returning cancels the leave delay.
        precondition(update(100, 3.7) == nil)
        precondition(update(100, 3.9) == nil && state.hidden)
        precondition(update(100, 4.1) == false)

        // Leaving early keeps SketchyBar and hides the native bar's retreat.
        precondition(update(0, 5, menu: true) == nil)
        precondition(update(300, 5.8, menu: true) == nil && !state.hidden)
        precondition(state.maskNative)
        precondition(update(300, 6.4) == nil && !state.maskNative) // Native bar gone.
        // Coming back restarts the delay.
        precondition(update(0, 6.5, menu: true) == nil)
        precondition(update(0, 5 + delay + 0.1, menu: true) == nil && !state.hidden)
        precondition(update(0, 6.5 + delay, menu: true) == true)
        precondition(update(nil, 10.1) == nil) // Leaving all displays restores it.
        precondition(update(nil, 10.5) == false)

        // Keyboard/menu-item activation (pointer away from the top) hides at once.
        precondition(update(400, 11, menu: true) == true)
        precondition(!state.maskNative)
        precondition(update(150, 11.1, down: true) == nil)
        precondition(update(150, 11.6, down: true) == nil && state.hidden)
        precondition(update(400, 12, menu: true) == nil) // Dropdown below the bar.
        precondition(update(400, 13, menu: true) == nil && state.hidden)
        precondition(update(400, 13.1) == nil)
        precondition(update(400, 13.5) == false)
        // An open SketchyBar menu owns the interaction, even at the native
        // reveal deadline. Hiding the bar would silently close this popup.
        state = HoverState()
        precondition(update(20, 20, menu: true) == nil)
        precondition(update(20, 20 + delay, down: true, menu: true) == nil,
                     "do not hide the bar between mouse-down and the popup callback")
        precondition(state.update(distance: 20, menuHeight: 36, mouseDown: false,
                                  menuVisible: true, now: 20 + delay + 0.1,
                                  popupVisible: true) == nil,
                     "native reveal must not consume the first popup click")
        precondition(!state.hidden && state.maskNative)
        precondition(state.update(distance: 120, menuHeight: 36, mouseDown: false,
                                  menuVisible: true, now: 30,
                                  popupVisible: true) == nil)
        precondition(!state.hidden, "the menu must remain available while choosing a row")
        precondition(update(20, 31, menu: true) == nil)
        precondition(update(20, 31 + delay, menu: true) == true,
                     "native menu access resumes after the popup closes")
        // The corner click must reveal immediately even in the suppression zone.
        state = HoverState()
        precondition(update(20, 40, menu: true) == nil && state.maskNative)
        state.revealNativeMenu()
        precondition(state.hidden && !state.maskNative)
        precondition(update(20, 40.1, down: true, menu: true) == nil && state.hidden)
        precondition(update(150, 41, menu: true) == nil && state.hidden)
        precondition(update(150, 42) == nil && state.hidden)
        precondition(update(150, 42.4) == false && !state.hidden)
        let display = CGRect(x: 0, y: 0, width: 1728, height: 1117)
        let popup = CGRect(x: 1421, y: 40, width: 191, height: 152)
        let cases: [(Int32, Int64, CGRect, Double, Bool)] = [
            (42, 101, popup, 1, true),
            (42, 0x8000_0065, popup, 1, true),
            (42, 101, CGRect(x: -9999, y: -9999, width: 180, height: 25), 1, false),
            (99, 101, popup, 1, false),
            (42, 3, popup, 1, false),
            (42, 101, popup, 0, false),
            (42, 101, .zero, 1, false),
        ]
        for (pid, layer, frame, alpha, expected) in cases {
            precondition(isSketchyBarPopup(ownerPID: pid, layer: layer, frame: frame,
                                          alpha: alpha, barPID: 42,
                                          displayBounds: [display]) == expected)
        }
        precondition(isSketchyBarPopup(ownerPID: 42, layer: 101,
            frame: CGRect(x: -1000, y: -500, width: 200, height: 150), alpha: 1,
            barPID: 42, displayBounds: [CGRect(x: -1728, y: -1117, width: 1728, height: 1117)]),
            "popups on monitors above or left of the main screen also count")
        print("SketchyBar hover state checks passed")
    }
}
