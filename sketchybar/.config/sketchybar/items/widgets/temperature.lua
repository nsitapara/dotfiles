local colors = require("colors")
local icons = require("icons")
local settings = require("settings")
local pending = false

local function cpu_temperature(result)
  if type(result) ~= "string" then return nil end
  -- CPU die average avoids incomplete per-core maps on the M4 Pro.
  -- TCMb is documented at github.com/dkorunic/iSMC/blob/master/src/temp.txt.
  for line in result:gmatch("[^\r\n]+") do
    local raw = line:match("^%[TCMb%]%s+(%S+)%s*$")
    local value = tonumber(raw)
    if value and value > 10 and value < 120 then return value end
  end
end

local temperature = sbar.add("graph", "widgets.temperature", 36, {
  position = "right",
  update_freq = 5,
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

local function update_temperature()
  if pending then return end
  pending = true
  -- Reuse the installed Stats reader without another daemon or parser process.
  sbar.exec("'/Applications/Stats.app/Contents/Resources/smc' list -t 2>/dev/null", function(result, exit_code)
    pending = false
    local value = cpu_temperature(result)
    if exit_code ~= 0 or not value then
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
      label = string.format("%d°C", math.floor(value + 0.5)),
    })
  end)
end

temperature:subscribe({ "routine", "system_woke" }, update_temperature)
update_temperature()
