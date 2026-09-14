-- Added immediately after the workspace group in both window-manager paths.
local colors = require("colors")

return function(yabai_active)
  local event = yabai_active and "yabai_mode_changed" or "aerospace_mode_changed"
  if not yabai_active then sbar.add("event", event) end
  local indicator = sbar.add("item", "wm.service", {
    position = "left", ignore_association = true, drawing = false, updates = true,
    icon = { drawing = false },
    label = {
      string = "SERVICE", color = colors.mauve,
      font = { size = 11.0, style = "Bold" }, padding_left = 9, padding_right = 9,
    },
    background = {
      drawing = true, color = colors.bg1, border_color = colors.mauve,
      border_width = 1, height = 26, corner_radius = 7,
    },
    padding_left = 4, padding_right = 8,
  })
  local generation = 0
  local function show(value)
    indicator:set({ drawing = value == "service" })
  end
  local function refresh()
    generation = generation + 1
    local request = generation
    local command = yabai_active and '"$HOME/.config/skhd/mode.sh" get'
      or "aerospace list-modes --current 2>/dev/null"
    sbar.exec('export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"; ' .. command, function(result)
      if request == generation then
        show(type(result) == "string" and result:match("^%s*(%S+)") or "")
      end
    end)
  end
  indicator:subscribe(event, function(env)
    if yabai_active then
      generation = generation + 1
      show(env.MODE)
    else
      refresh()
    end
  end)
  indicator:subscribe({ "system_woke", "display_change" }, refresh)
  refresh()
end
