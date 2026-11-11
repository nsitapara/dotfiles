local colors = require("colors")
local icons = require("icons")
local settings = require("settings")

local ssd = sbar.add("item", "widgets.ssd", {
  position = "right",
  icon = {
    string = icons.disk,
    padding_left = 5,
    padding_right = 3,
    font = { style = settings.font.style_map["Regular"], size = 14.0 },
  },
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
  click_script = "open -a Finder /",
})

sbar.add("bracket", "widgets.ssd.bracket", { ssd.name }, {
  background = { color = colors.bg1 },
})

sbar.add("item", "widgets.ssd.padding", {
  position = "right",
  width = settings.group_paddings,
})

-- White under 80%, then yellow, orange and red as the disk fills up.
local function usage_color(used)
  if used < 80 then return colors.white end
  if used < 90 then return colors.yellow end
  if used < 95 then return colors.orange end
  return colors.red
end

-- Fed by the system_stats provider started in widgets/init.lua: space used
-- across the APFS container. The provider sends it only every 5 minutes and
-- after wake; ticks without a disk reading leave this widget untouched.
ssd:subscribe("system_stats", function(env)
  if env.disk == nil then return end
  local used = tonumber(env.disk)
  if not used or used < 0 or used > 100 then
    ssd:set({ label = { string = "--%", color = colors.white } })
    return
  end
  ssd:set({ label = { string = string.format("%02d%%", used), color = usage_color(used) } })
end)
