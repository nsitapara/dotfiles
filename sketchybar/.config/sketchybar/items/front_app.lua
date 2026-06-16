local colors = require("colors")
local settings = require("settings")

-- [PROTO] native icon of the focused app, shown directly in front of its name
local front_app_icon = sbar.add("item", "front_app.icon", {
  display = "active",
  icon = { drawing = false },
  label = { drawing = false },
  background = {
    color = colors.transparent,
    border_width = 0,
    image = { scale = 0.6, corner_radius = 5, drawing = true },
  },
  padding_left = 8,
  padding_right = 2,
  updates = true,
})

local front_app = sbar.add("item", "front_app", {
  display = "active",
  icon = { drawing = false },
  label = {
    font = {
      style = settings.font.style_map["Black"],
      size = 12.0,
    },
  },
  updates = true,
})

front_app:subscribe("front_app_switched", function(env)
  front_app:set({ label = { string = env.INFO } })
  front_app_icon:set({ background = { image = "app." .. env.INFO } })
end)
