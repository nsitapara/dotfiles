local colors = require("colors")
local icons = require("icons")
local settings = require("settings")

local temperature = sbar.add("item", "widgets.temperature", {
  position = "right",
  icon = {
    string = icons.temperature,
    padding_left = 5,
    padding_right = 3,
    font = { style = settings.font.style_map["Regular"], size = 14.0 },
  },
  label = {
    string = "—",
    padding_left = 0,
    padding_right = 5,
    font = {
      family = settings.font.numbers,
      style = settings.font.style_map["Semibold"],
      size = 13.0,
    },
  },
  click_script = "open -a 'Activity Monitor'",
})

sbar.add("bracket", "widgets.temperature.bracket", { temperature.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.temperature.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- Green at normal Apple Silicon die temperatures, yellow when warm, red when hot.
local function heat_color(value)
  if value < 70 then return colors.green end
  if value < 90 then return colors.yellow end
  return colors.red
end

-- Fed by the system_stats provider started in widgets/init.lua: the CPU die
-- average (SMC key TCMb), which avoids incomplete per-core maps on the M4 Pro.
temperature:subscribe("system_stats", function(env)
  local value = tonumber(env.temp)
  if not value or value ~= value or value <= 10 or value >= 120 then
    temperature:set({ icon = { color = colors.white }, label = { string = "—" } })
    return
  end
  temperature:set({
    icon = { color = heat_color(value) },
    label = { string = string.format("%02dC", math.floor(value + 0.5)) },
  })
end)
