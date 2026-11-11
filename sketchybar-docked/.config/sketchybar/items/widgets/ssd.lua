local colors = require("colors")
local icons = require("icons")
local settings = require("settings")

local ssd = sbar.add("graph", "widgets.ssd", 36, {
  position = "right",
  graph = { color = colors.blue },
  icon = {
    string = icons.disk,
    width = 22,
    align = "center",
    font = { style = settings.font.style_map["Regular"], size = 14.0 },
  },
  label = {
    string = "--%",
    padding_right = 2,
    font = {
      family = settings.font.numbers,
      style = settings.font.style_map["Semibold"],
      size = 13.0,
    },
    align = "right",
    width = 0,
    y_offset = 4,
  },
  padding_left = 5,
  padding_right = settings.paddings + 6,
  background = {
    height = 22,
    drawing = true,
    color = { alpha = 0 },
    border_color = { alpha = 0 },
  },
  click_script = "open -a Finder /",
})

sbar.add("bracket", "widgets.ssd.bracket", { ssd.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.ssd.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- Fed by the system_stats provider started in widgets/init.lua: space used
-- across the APFS container, as the label and as the graph. The provider sends
-- it only every 5 minutes and after wake, so the graph spans about 3 hours.
ssd:subscribe("system_stats", function(env)
  if env.disk == nil then return end
  local used = tonumber(env.disk)
  if not used or used < 0 or used > 100 then
    ssd:set({ label = "--%" })
    return
  end
  -- Match the other widgets' lower-third trace below the percentage label.
  ssd:push({ used / 100 * 0.3 })
  ssd:set({ label = string.format("%02d%%", used) })
end)
