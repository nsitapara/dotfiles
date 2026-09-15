-- Loaded by either existing SketchyBar profile during the yabai trial.
local colors = require("colors")
local settings = require("settings")
local pills = {}
local busy = false
local pending = false

-- sbar.exec runs in a launchd environment that may omit Homebrew.
local prefix = "export PATH=\"$PATH:/opt/homebrew/bin:/usr/local/bin\"; "
sbar.add("event", "yabai_windows_changed")
sbar.add("event", "yabai_mode_changed")

local mode = sbar.add("item", "yabai.mode", {
  position = "left", drawing = false, updates = true,
  icon = { drawing = false },
  label = { string = "", color = colors.mauve },
})
mode:subscribe("yabai_mode_changed", function(env)
  local value = env.MODE or "default"
  mode:set({ drawing = value ~= "default" and value ~= "service", label = { string = value } })
end)

local function create_pill(index)
  local item = sbar.add("item", "yabai.space." .. index, {
    position = "left", drawing = false,
    icon = {
      font = { family = settings.font.numbers, size = 14.0 },
      padding_left = 10, padding_right = 10,
    },
    label = { drawing = false },
    background = { drawing = false },
    padding_left = 2, padding_right = 2,
  })
  local pill = { item = item, slots = {} }
  local members = { item.name }
  local function clicked()
    -- The index comes from yabai's numeric JSON, never from an app title.
    if pill.index then
      sbar.exec(prefix .. '/usr/bin/python3 "$HOME/.config/yabai/scripts/focus-space.py" ' .. pill.index)
    else
      sbar.exec(prefix .. '"$HOME/.config/yabai/scripts/ensure-spaces.sh" && sketchybar --trigger yabai_windows_changed')
    end
  end
  item:subscribe("mouse.clicked", clicked)
  for slot_index = 1, 5 do
    local slot = sbar.add("item", "yabai.space." .. index .. ".app." .. slot_index, {
      position = "left", drawing = false, width = 29,
      padding_left = 0, padding_right = 0,
      icon = { drawing = false }, label = { drawing = false },
      background = {
        drawing = true, color = colors.transparent, border_width = 0, height = 24,
        image = { drawing = true, scale = 0.7, corner_radius = 5 },
      },
    })
    slot:subscribe("mouse.clicked", clicked)
    pill.slots[slot_index] = slot
    members[#members + 1] = slot.name
  end
  pill.trail = sbar.add("item", "yabai.space." .. index .. ".trail", {
    position = "left", drawing = false, width = 4,
    padding_left = 0, padding_right = 0,
    icon = { drawing = false }, label = { drawing = false },
    background = { drawing = false },
  })
  members[#members + 1] = pill.trail.name
  pill.bracket = sbar.add("bracket", "yabai.space." .. index .. ".bracket", members, {
    drawing = false,
    background = { color = colors.bg1, border_color = colors.bg2,
      border_width = 2, height = 30, corner_radius = 9 },
  })
  pill.padding = sbar.add("item", "yabai.space." .. index .. ".padding", {
    position = "left", drawing = false, width = settings.group_paddings,
    icon = { drawing = false }, label = { drawing = false },
    background = { drawing = false },
  })
  pills[index] = pill
  return pill
end

-- Reserve the workspace group before the rest of the theme adds its widgets.
-- Creating these only in the asynchronous query callback put them at the end.
for index = 1, 9 do create_pill(index) end

local function render(spaces, windows, displays, bar_displays, layout)
  -- Join by CoreGraphics display ID. Yabai's arrangement order need not match
  -- SketchyBar's arrangement order, especially when the laptop lid opens.
  local arrangement_by_id, display_map = {}, {}
  for _, display in ipairs(bar_displays) do
    local id = display.DirectDisplayID or display.id
    if id then arrangement_by_id[id] = display["arrangement-id"] end
  end
  for _, display in ipairs(displays) do
    display_map[display.index] = arrangement_by_id[display.id]
  end
  local ordered = {}
  for _, display in ipairs(displays) do ordered[#ordered + 1] = display end
  table.sort(ordered, function(a, b)
    if a.frame.x == b.frame.x then return a.frame.y < b.frame.y end
    return a.frame.x < b.frame.x
  end)
  local planned = {}
  for _, screen in ipairs(layout or {}) do
    for _, workspace in ipairs(screen.workspaces or {}) do
      planned[workspace] = arrangement_by_id[screen.id]
    end
  end
  local apps_by_space, seen_apps = {}, {}
  for _, window in ipairs(windows) do
    local id, app = window.space, window.app
    apps_by_space[id] = apps_by_space[id] or {}
    seen_apps[id] = seen_apps[id] or {}
    -- Chrome gets one icon per window; other apps remain grouped.
    if app and app ~= "" and (app == "Google Chrome" or not seen_apps[id][app]) and not window["is-hidden"] then
      seen_apps[id][app] = true
      table.insert(apps_by_space[id], app)
    end
  end
  local seen = {}
  for _, space in ipairs(spaces) do
    if not space["is-native-fullscreen"] and type(space.index) == "number" then
      local number = tonumber((space.label or ""):match("^ws([1-9])$"))
      local key = number or ("native" .. space.index)
      seen[key] = true
      local pill = pills[key] or create_pill(key)
      pill.index = space.index
      local display = display_map[space.display]
      local visible = display ~= nil
      local focused = space["has-focus"]
      local label = (space.label or ""):match("^ws([1-9])$") or ("D" .. space.index)
      local apps = apps_by_space[space.index] or {}
      pill.item:set({ drawing = visible, display = display or "active", icon = {
        string = label,
        padding_left = #apps == 0 and 12 or 10,
        padding_right = #apps == 0 and 12 or 5,
      } })
      pill.bracket:set({ drawing = visible, display = display or "active" })
      sbar.animate("sin", 14, function()
        pill.item:set({ icon = { color = focused and colors.mauve or colors.white,
        font = { size = focused and 18.0 or 14.0 },
        } })
        pill.bracket:set({ background = {
        color = focused and colors.bg2 or colors.bg1,
        border_color = focused and colors.mauve or colors.bg2,
        height = focused and 36 or 30, corner_radius = focused and 11 or 9,
        } })
      end)
      pill.trail:set({ drawing = visible and #apps > 0, display = display or "active" })
      pill.padding:set({ drawing = visible, display = display or "active" })
      for i, slot in ipairs(pill.slots) do
        local app = (apps_by_space[space.index] or {})[i]
        slot:set({ drawing = visible and app ~= nil, display = display or "active",
          background = { image = app and ("app." .. app) or "" } })
      end
    end
  end
  for index, pill in pairs(pills) do
    if not seen[index] then
      -- Match AeroSpace's persistent workspace bar. Missing native Spaces
      -- are dimmed; clicking one retries automatic desktop setup.
      local target = type(index) == "number" and index <= 6 and ordered[(#ordered >= 2 and index % 2 == 0) and 2 or 1] or nil
      local display = planned[index]
      if not layout or #layout == 0 then display = target and display_map[target.index] end
      local visible = display ~= nil
      pill.index = nil
      pill.item:set({ drawing = visible, display = display or "active", icon = {
        string = tostring(index), color = colors.grey or colors.white,
        font = { size = 14.0 }, padding_left = 12, padding_right = 12,
      } })
      pill.bracket:set({ drawing = visible, display = display or "active", background = {
        color = colors.bg1, border_color = colors.bg2, height = 30, corner_radius = 9,
      } })
      pill.trail:set({ drawing = false })
      pill.padding:set({ drawing = visible, display = display or "active" })
      for _, slot in ipairs(pill.slots) do slot:set({ drawing = false }) end
    end
  end
end

local update
update = function()
  if busy then pending = true; return end
  busy = true
  -- Combine JSON once, and let SbarLua decode it. A failed query leaves the
  -- last complete frame visible instead of clearing the bar during a hotplug.
  local command = prefix .. [[
    spaces=$(yabai -m query --spaces) &&
    windows=$(yabai -m query --windows) &&
    displays=$(yabai -m query --displays) &&
    bar_displays=$(sketchybar --query displays) &&
    layout=$(cat "$HOME/.local/state/dotfiles-wm/display-layout.json" 2>/dev/null || echo '[]') &&
    jq -n --argjson spaces "$spaces" --argjson windows "$windows" \
      --argjson displays "$displays" --argjson bar_displays "$bar_displays" --argjson layout "$layout" \
      '{spaces:$spaces, windows:$windows, displays:$displays, bar_displays:$bar_displays, layout:$layout}'
  ]]
  sbar.exec(command, function(result)
    if type(result) == "table" and type(result.spaces) == "table"
      and type(result.windows) == "table" and type(result.displays) == "table"
      and type(result.bar_displays) == "table" then
      render(result.spaces, result.windows, result.displays, result.bar_displays, result.layout)
    end
    busy = false
    if pending then pending = false; update() end
  end)
end
local observer = sbar.add("item", "yabai.observer", { drawing = false, updates = true })
observer:subscribe({ "space_change", "space_windows_change",
  "system_woke", "yabai_windows_changed" }, update)
-- Profiles are pinned from the bar menu (wm.sh profile); a display change only
-- refreshes the pills. See DISPLAY-MODES.md.
observer:subscribe("display_change", update)
update()
