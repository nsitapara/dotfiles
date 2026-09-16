-- Added immediately after the workspace group in both window-manager paths.
local colors = require("colors")

return function(manager)
  local rift_active = manager == "rift"
  local yabai_active = manager == true or manager == "yabai" or rift_active
  local event = rift_active and "rift_mode_changed" or (yabai_active and "yabai_mode_changed" or "aerospace_mode_changed")
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
  sbar.add("event", "wm_help_toggle")
  local help_visible, help_built, current_mode = false, false, nil
  local function build_help()
    if help_built then return end
    help_built = true
    local rows = {
      {"SERVICE MODE", rift_active and "Rift + skhd" or (yabai_active and "yabai + skhd" or "AeroSpace"), true},
      {"?  /  Shift + /", "Show or hide this help"},
      {"Esc / Space / F15", "Close help and return to normal mode"},
      {"F", "Toggle floating; return to normal mode"},
      {"R", yabai_active and "Restore tiled layout and balance sizes" or "Flatten layout; return to normal mode"},
      {"Up / Down", "Volume up / down"},
      {"Shift + Down", "Mute volume"},
    }
    if rift_active then
      rows[#rows+1] = {"B / T / S", "BSP / flexible splits / full-workspace stack"}
      rows[#rows+1] = {"M / C", "Master and stack / scrolling columns"}
      rows[#rows+1] = {"G / U", "Toggle group stack / unjoin in flexible splits"}
    end
    if not yabai_active then
      rows[#rows+1] = {"Cmd + Shift + arrows", "Join with neighbor; return to normal mode"}
      rows[#rows+1] = {"Backspace", "Close ALL other windows; return to normal mode"}
    end
    local normal = {
      {"NORMAL MODE", "Press Esc before using these shortcuts", true},
      {"Cmd + arrows", "Focus windows, continuing across monitors"},
      {"Cmd + Shift + arrows", "Swap, fill a side, then cross monitors"},
      {"Cmd + 1–9", "Switch workspace"},
      {"Cmd + Shift + 1–9", "Move window to workspace and follow it"},
      {"Cmd + Ctrl + Shift + 1–9", "Send window to workspace; stay here"},
      {"Alt + Tab", "Return to the previous workspace"},
      {"Ctrl + Tab", "Return to the previously focused window"},
      {"Cmd + F", "Toggle window fullscreen within the workspace"},
      {"Cmd + Ctrl + Shift + F", "Toggle floating"},
      {"Cmd + 0 / Cmd + Ctrl + 0", rift_active and "Rebuild the workspace with default BSP sizes" or "Balance window sizes"},
      {"Cmd + J", "Change split orientation"},
      {"Cmd + comma", yabai_active and "Toggle tiled / stacked layout" or "Toggle tiles / accordion layout"},
      {"Cmd + = / minus", "Increase / decrease width"},
      {"Cmd + Shift + = / minus", "Increase / decrease height"},
      {"Cmd + Ctrl + = / minus", "Step column width: 50%, 65%, 75%"},
      {"Cmd + Ctrl + Left / Right", "Move window between monitors; wrap and follow"},
      {"Cmd + Alt + S / F14", "Enter service mode"},
      {"Cmd + Ctrl + Alt + Shift", "Add R: resize, W: workspace, M: " .. (rift_active and "join" or (yabai_active and "insertion" or "merge"))},
    }
    for _, row in ipairs(normal) do rows[#rows+1] = row end
    for i, row in ipairs(rows) do
      sbar.add("item", "wm.help." .. i, {
        position = "popup.wm.service", width = 640,
        padding_left = 0, padding_right = 0,
        icon = {
          string = row[1], width = 220, align = "left",
          padding_left = 14, padding_right = 8,
          color = row[3] and colors.mauve or colors.white,
          font = { family = "SF Pro", size = 12.0, style = row[3] and "Bold" or "Regular" },
        },
        label = {
          string = row[2], align = "left", padding_left = 4, padding_right = 14,
          color = row[3] and colors.mauve or colors.white,
          font = { family = "SF Pro", size = 12.0 },
        },
        background = { drawing = false },
      })
    end
  end
  indicator:set({ popup = {
    drawing = false, align = "left", height = 25,
    background = { color = colors.bg1, border_color = colors.mauve,
      border_width = 1, corner_radius = 9 },
  } })
  local function set_help(visible)
    help_visible = visible
    if visible then build_help() end
    indicator:set({ popup = { drawing = visible } })
  end
  local generation = 0
  local function show(value)
    current_mode = value
    if value ~= "service" then set_help(false) end
    indicator:set({ drawing = value == "service" })
  end
  local function refresh(after)
    generation = generation + 1
    local request = generation
    local command = yabai_active and '"$HOME/.config/skhd/mode.sh" get'
      or "aerospace list-modes --current 2>/dev/null"
    sbar.exec('export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"; ' .. command, function(result)
      if request == generation then
        show(type(result) == "string" and result:match("^%s*(%S+)") or "")
        if type(after) == "function" then after() end
      end
    end)
  end
  local function toggle_help()
    if current_mode == "service" then
      set_help(not help_visible)
    else
      -- A fast ? press can arrive before the mode-change query completes.
      refresh(function()
        if current_mode == "service" then set_help(not help_visible) end
      end)
    end
  end
  indicator:subscribe("wm_help_toggle", toggle_help)
  indicator:subscribe("mouse.clicked", toggle_help)
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
