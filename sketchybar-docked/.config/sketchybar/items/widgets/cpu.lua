local icons = require("icons")
local colors = require("colors")
local settings = require("settings")

local cpu = sbar.add("item", "widgets.cpu", {
  position = "right",
  icon = { string = icons.cpu, padding_left = 5, padding_right = 3 },
  label = {
    string = "--%",
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

-- White when idle, then yellow, orange and red as load climbs.
local function load_color(load)
  if load <= 30 then return colors.white end
  if load < 60 then return colors.yellow end
  if load < 80 then return colors.orange end
  return colors.red
end

-- Fed by the system_stats provider started in widgets/init.lua.
cpu:subscribe("system_stats", function(env)
  local load = tonumber(env.cpu)
  if not load or load < 0 or load > 100 then
    cpu:set({ label = { string = "--%", color = colors.white } })
    return
  end
  cpu:set({ label = { string = string.format("%02d%%", load), color = load_color(load) } })
end)

sbar.add("bracket", "widgets.cpu.bracket", { cpu.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.cpu.padding", {
  position = "right",
  width = settings.group_paddings,
})
