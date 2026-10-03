-- Require the sketchybar module
sbar = require("sketchybar")

-- Set the bar name, if you are using another bar instance than sketchybar
-- sbar.set_bar_name("bottom_bar")

-- Register custom aerospace event
sbar.add("event", "aerospace_workspace_change")

-- Bundle the entire initial configuration into a single message to sketchybar
sbar.begin_config()
require("bar")
require("default")
require("items")
sbar.add("item", "display_mode", { drawing = false, label = { string = "docked" } })
sbar.end_config()

-- Hide SketchyBar while the native menu bar is in use.
sbar.exec('/usr/bin/python3 "$HOME/dotfiles/sketchybar-hover/run.py"')

-- Run the event loop of the sketchybar module (without this there will be no
-- callback functions executed in the lua module)
sbar.event_loop()
