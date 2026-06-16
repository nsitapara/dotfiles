local colors = require("colors")
local settings = require("settings")

-- Center: focused app's native icon + name, grouped in one pill.
-- (position = "center" lays items out left-to-right in add order, so the icon
-- is added before the label to read [icon] [name].)

local center_icon = sbar.add("item", "center_app.icon", {
  position = "center",
  display = "active",
  icon = { drawing = false },
  label = { drawing = false },
  width = 26, -- background.image does NOT auto-size; pin a box so it can't overflow
  padding_left = 8,
  padding_right = 4,
  background = {
    color = colors.transparent,
    border_width = 0,
    image = { scale = 0.6, corner_radius = 5, drawing = true },
  },
  updates = true,
})

local center_label = sbar.add("item", "center_app.label", {
  position = "center",
  display = "active",
  icon = { drawing = false },
  label = {
    font = { style = settings.font.style_map["Black"], size = 12.0 },
    color = colors.white,
  },
  padding_left = 0,
  padding_right = 10,
  updates = true,
})

-- the bracket IS the pill grouping icon + name. Matches the right-side widget
-- pills (default.lua): bg1 fill + soft bg2 2px border.
sbar.add("bracket", "center_app.bracket", { center_icon.name, center_label.name }, {
  background = {
    color = colors.bg1,
    border_color = colors.bg2,
    border_width = 2,
    height = 30,
    corner_radius = 9,
  },
})

local function set_app(name)
  name = (name or ""):gsub("%s+$", "")
  if name ~= "" then
    center_icon:set({ background = { image = "app." .. name } })
    center_label:set({ label = { string = name } })
  end
end

center_label:subscribe("front_app_switched", function(env)
  set_app(env.INFO)
end)

-- Seed the current front app on load (the event only fires on change)
sbar.exec(
  "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'",
  function(result)
    set_app(result)
  end
)
