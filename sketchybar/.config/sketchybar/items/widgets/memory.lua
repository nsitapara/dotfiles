local icons = require("icons")
local colors = require("colors")
local settings = require("settings")
local pending = false

local function memory_fraction(result)
  if type(result) ~= "string" then return nil end
  local total = tonumber(result:match("^%s*(%d+)%s*\n"))
  local page_size = tonumber(result:match("page size of (%d+) bytes"))
  local anonymous = tonumber(result:match("Anonymous pages:%s*(%d+)%."))
  local purgeable = tonumber(result:match("Pages purgeable:%s*(%d+)%."))
  local wired = tonumber(result:match("Pages wired down:%s*(%d+)%."))
  local compressed = tonumber(result:match("Pages occupied by compressor:%s*(%d+)%."))
  if not total or total <= 0 or not page_size or page_size <= 0
      or not anonymous or not purgeable or not wired or not compressed then
    return nil
  end
  -- Estimate app + wired + compressed RAM, excluding reclaimable file cache
  -- and purgeable pages. Count the compressor's physical size, not stored pages.
  local used = (math.max(0, anonymous - purgeable) + wired + compressed) * page_size
  return math.min(1, used / total)
end

local memory = sbar.add("graph", "widgets.memory", 36, {
  position = "right",
  update_freq = 5,
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

local function update_memory()
  if pending then return end
  pending = true
  sbar.exec("/usr/sbin/sysctl -n hw.memsize && /usr/bin/vm_stat", function(result, exit_code)
    pending = false
    local fraction = memory_fraction(result)
    if exit_code ~= 0 or not fraction then
      memory:set({ label = "--%" })
      return
    end
    -- Match CPU's lower-third trace. Usage alone does not indicate pressure.
    memory:push({ fraction * 0.3 })
    memory:set({ label = string.format("%d%%", math.floor(fraction * 100 + 0.5)) })
  end)
end

memory:subscribe({ "routine", "system_woke" }, update_memory)
update_memory()
