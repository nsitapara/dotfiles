local icons = require("icons")
local colors = require("colors")
local settings = require("settings")

local memory = sbar.add("graph", "widgets.memory", 36, {
  position = "right",
  graph = { color = colors.blue },
  background = {
    height = 22,
    color = { alpha = 0 },
    border_color = { alpha = 0 },
    drawing = true,
  },
  icon = { string = icons.memory, width = 22, align = "center" },
  label = {
    string = "--%",
    font = {
      family = settings.font.numbers,
      style = settings.font.style_map["Semibold"],
      size = 13.0,
    },
    align = "right",
    padding_right = 2,
    width = 0,
    y_offset = 4,
  },
  padding_right = settings.paddings + 6,
  click_script = "open -a 'Activity Monitor'",
})

sbar.add("bracket", "widgets.memory.bracket", { memory.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.memory.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- Fed by the system_stats provider started in widgets/init.lua. It counts
-- app + wired + compressed RAM, excluding reclaimable cache and purgeable pages.
memory:subscribe("system_stats", function(env)
  local percent = tonumber(env.mem)
  if not percent or percent < 0 or percent > 100 then
    memory:set({ label = "--%" })
    return
  end
  -- Match CPU's lower-third trace. Usage alone does not indicate pressure.
  memory:push({ percent / 100 * 0.3 })
  memory:set({ label = string.format("%d%%", math.floor(percent + 0.5)) })
end)
