local colors = require("colors")

-- Leading padding
sbar.add("item", { width = 6 })

-- Far-left standalone pill: the focused app's native macOS icon (this replaces
-- the old focused-workspace-number indicator that used to live here).
local front_icon = sbar.add("item", "front_app.icon", {
  display = "active",
  icon = { drawing = false },
  label = { drawing = false },
  width = 30, -- background.image does NOT auto-size; pin a box so it can't overflow
  padding_left = 6, -- breathing room inside the pill so the icon isn't cramped
  padding_right = 6,
  background = {
    color = colors.transparent,
    border_width = 0,
    image = { scale = 0.7, corner_radius = 6, drawing = true },
  },
  updates = true,
})

-- Padding after the icon (no pill/bracket behind the selected-app icon)
sbar.add("item", { width = 7 })

front_icon:subscribe("front_app_switched", function(env)
  front_icon:set({ background = { image = "app." .. env.INFO } })
end)

-- Seed the current front app on load (the event only fires on change)
sbar.exec(
  "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'",
  function(result)
    local app = (result or ""):gsub("%s+$", "")
    if app ~= "" then
      front_icon:set({ background = { image = "app." .. app } })
    end
  end
)
