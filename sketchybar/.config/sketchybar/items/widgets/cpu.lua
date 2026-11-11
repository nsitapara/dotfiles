local icons = require("icons")
local colors = require("colors")
local settings = require("settings")

local cpu = sbar.add("graph", "widgets.cpu" , 36, {
  position = "right",
  graph = { color = colors.blue },
  background = {
    height = 22,
    color = { alpha = 0 },
    border_color = { alpha = 0 },
    drawing = true,
  },
  icon = { string = icons.cpu, width = 22, align = "center" },
  label = {
    string = "??%",
    font = {
      family = settings.font.numbers,
      style = settings.font.style_map["Semibold"],
      size = 13.0,
    },
    align = "right",
    padding_right = 2,
    width = 0,
    y_offset = 4
  },
  padding_right = settings.paddings + 6
})

-- Fed by the system_stats provider started in widgets/init.lua.
cpu:subscribe("system_stats", function(env)
  local load = tonumber(env.cpu)
  if not load or load < 0 or load > 100 then return end
  -- Keep the graph in the lower third, below the percentage label.
  cpu:push({ load / 100. * 0.3 })

  local color = colors.blue
  if load > 30 then
    if load < 60 then
      color = colors.yellow
    elseif load < 80 then
      color = colors.orange
    else
      color = colors.red
    end
  end

  cpu:set({
    graph = { color = color },
    label = string.format("%02d%%", load),
  })
end)

cpu:subscribe("mouse.clicked", function(env)
  sbar.exec("open -a 'Activity Monitor'")
end)

-- Background around the cpu item
sbar.add("bracket", "widgets.cpu.bracket", { cpu.name }, {
  background = { color = colors.bg1 }
})

-- Background around the cpu item
sbar.add("item", "widgets.cpu.padding", {
  position = "right",
  width = settings.group_paddings
})
