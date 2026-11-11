local colors = require("colors")
local icons = require("icons")
local settings = require("settings")

local temperature = sbar.add("graph", "widgets.temperature", 36, {
  position = "right",
  graph = { color = colors.blue },
  background = {
    height = 22,
    color = { alpha = 0 },
    border_color = { alpha = 0 },
    drawing = true,
  },
  icon = {
    string = icons.temperature,
    width = 22,
    align = "center",
    font = { style = settings.font.style_map["Regular"], size = 14.0 },
  },
  label = {
    string = "—",
    width = 0,
    align = "right",
    padding_right = 2,
    y_offset = 4,
    font = {
      family = settings.font.numbers,
      style = settings.font.style_map["Semibold"],
      size = 13.0,
    },
  },
  padding_right = settings.paddings + 6,
  click_script = "open -a 'Activity Monitor'",
})

sbar.add("bracket", "widgets.temperature.bracket", { temperature.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.temperature.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- Fed by the system_stats provider started in widgets/init.lua: the CPU die
-- average (SMC key TCMb), which avoids incomplete per-core maps on the M4 Pro.
temperature:subscribe("system_stats", function(env)
  local value = tonumber(env.temp)
  if not value or value ~= value or value <= 10 or value >= 120 then
    temperature:set({ label = "—" })
    return
  end
  -- Match the CPU graph's lower-third trace and color bands.
  temperature:push({ math.min(value / 100, 1) * 0.3 })
  local color = colors.blue
  if value > 30 then
    if value < 60 then
      color = colors.yellow
    elseif value < 80 then
      color = colors.orange
    else
      color = colors.red
    end
  end
  temperature:set({
    graph = { color = color },
    label = string.format("%02dC", math.floor(value + 0.5)),
  })
end)
