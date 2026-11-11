local icons = require("icons")
local colors = require("colors")
local settings = require("settings")

local memory = sbar.add("item", "widgets.memory", {
  position = "right",
  icon = { string = icons.memory, padding_left = 5, padding_right = 3 },
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

sbar.add("bracket", "widgets.memory.bracket", { memory.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.memory.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- Green under 70%, yellow under 90%, red when RAM is nearly full.
local function usage_color(percent)
  if percent < 70 then return colors.green end
  if percent < 90 then return colors.yellow end
  return colors.red
end

-- Fed by the system_stats provider started in widgets/init.lua. It counts
-- app + wired + compressed RAM, excluding reclaimable cache and purgeable pages.
memory:subscribe("system_stats", function(env)
  local percent = tonumber(env.mem)
  if not percent or percent < 0 or percent > 100 then
    memory:set({ icon = { color = colors.white }, label = { string = "--%" } })
    return
  end
  memory:set({
    icon = { color = usage_color(percent) },
    label = { string = string.format("%02d%%", math.floor(percent + 0.5)) },
  })
end)
