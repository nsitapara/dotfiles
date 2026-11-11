local colors = require("colors")
local icons = require("icons")
local settings = require("settings")
local activity = {}

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

local function push_activity(mbps)
  table.insert(activity, mbps)
  if #activity > 36 then table.remove(activity, 1) end

  -- Rescale the whole history together; a 10 MB/s floor keeps idle noise small.
  local peak = 10
  for _, sample in ipairs(activity) do peak = math.max(peak, sample) end
  local graph = {}
  for _ = 1, 36 - #activity do table.insert(graph, 0) end
  for _, sample in ipairs(activity) do
    -- Reserve the lower third for the graph, below the percentage label.
    table.insert(graph, sample / peak * 0.3)
  end
  ssd:push(graph)
end

-- Fed by the system_stats provider started in widgets/init.lua. The label is
-- space used across the APFS container (refreshed every 5 minutes); the graph
-- is disk0 read + write throughput. Disk values arrive only on the provider's
-- slower disk ticks; CPU-only ticks leave this widget untouched.
ssd:subscribe("system_stats", function(env)
  if env.disk == nil then return end
  local used = tonumber(env.disk)
  if used and used >= 0 and used <= 100 then
    ssd:set({ label = string.format("%d%%", used) })
  else
    ssd:set({ label = "--%" })
  end
  local mbps = tonumber(env.disk_mbps)
  if mbps and mbps >= 0 and mbps == mbps and mbps < math.huge then push_activity(mbps) end
end)
