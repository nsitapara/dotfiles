-- Use yabai's icon slots, grouping, spacing, colors and animation.
local adapter = { name = "rift" }
local targets = {}
local pending, dirty, epoch, retries = false, false, 0, 0
function adapter.click(index)
  local target = targets[index]
  if target then
    sbar.exec('/usr/bin/python3 "$HOME/.config/rift/adapter.py" action workspace-display '
      .. target.number .. ' ' .. target.uuid)
  end
end
function adapter.start(render)
  local refresh
  refresh = function()
    if pending then dirty = true; return end
    pending = true
    local requested = epoch
    sbar.exec('/usr/bin/python3 "$HOME/.config/rift/adapter.py" bar', function(data)
      pending = false
      local valid = requested == epoch and type(data) == "table" and type(data.spaces) == "table"
      if valid then
        targets = {}
        for _, target in ipairs(data.targets) do targets[target.index] = target end
        render(data.spaces, data.windows, data.displays, data.bar_displays, data.layout)
        retries = 0
      end
      if dirty then dirty = false; refresh()
      elseif not valid and retries < 3 then
        retries = retries + 1
        sbar.delay(0.2 * retries, refresh)
      end
    end)
  end
  sbar.add("event", "rift_changed")
  local watcher = sbar.add("item", "rift.events", { drawing = false, updates = true })
  watcher:subscribe("rift_changed", function() retries = 0; refresh() end)
  watcher:subscribe({ "system_woke", "display_change" }, function()
    epoch = epoch + 1; retries = 0; refresh()
  end)
  refresh()
end
assert(loadfile(os.getenv("HOME") .. "/dotfiles/yabai/.config/yabai/sketchybar.lua"))(adapter)
