local colors = require("colors")
local icons = require("icons")
local settings = require("settings")
local activity = {}
local activity_pending = false
local last_storage_update = 0

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
  update_freq = 2,
  click_script = "open -a Finder /",
})

local function update_storage()
  last_storage_update = os.time()
  -- APFS volumes share container space. Total minus available includes the
  -- system and sibling volumes, unlike df's per-volume Used/Capacity columns.
  sbar.exec("df -kP /System/Volumes/Data", function(result)
    local total, available = result:match("\n%S+%s+(%d+)%s+%d+%s+(%d+)")
    total, available = tonumber(total), tonumber(available)
    if not total or total <= 0 or not available then
      ssd:set({ label = "--%" })
      return
    end
    local fraction = (total - available) / total
    local used = math.floor(100 * fraction + 0.5)
    ssd:set({ label = used .. "%" })
  end)
end

local function update_activity()
  if activity_pending then return end
  activity_pending = true
  -- The first iostat sample is a since-boot average; use the second interval.
  sbar.exec("LC_ALL=C /usr/sbin/iostat -d -w 1 -c 2 disk0", function(result, exit_code)
    activity_pending = false
    if exit_code ~= 0 then return end
    local mbps, samples = nil, 0
    for line in result:gmatch("[^\r\n]+") do
      local size, transfers, rate = line:match("^%s*(%S+)%s+(%S+)%s+(%S+)%s*$")
      if tonumber(size) and tonumber(transfers) and tonumber(rate) then
        mbps = tonumber(rate)
        samples = samples + 1
      end
    end
    if samples < 2 or not mbps then return end
    table.insert(activity, math.max(0, mbps))
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
  end)
end

sbar.add("bracket", "widgets.ssd.bracket", { ssd.name }, {
  background = { color = colors.bg1 },
})

ssd:subscribe({ "routine", "system_woke" }, function(env)
  if env.SENDER == "system_woke" or os.time() - last_storage_update >= 60 then
    update_storage()
  end
  update_activity()
end)
update_storage()
update_activity()
