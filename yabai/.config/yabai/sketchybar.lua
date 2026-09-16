-- Loaded by either existing SketchyBar profile during the yabai trial.
local colors = require("colors")
local settings = require("settings")
local pills = {}
local busy = false
local pending = false
local topology
local topology_epoch = 0
local retry_count, retry_token = 0, 0
local retry_delays = { 0.1, 0.25, 0.5 }
local last_snapshot
local removed_windows = {}
local window_epoch, settle_token = 0, 0

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

-- Remember the properties sent to each item, including nested image/style fields.
local rendered = {}
local function changed_properties(previous, values)
  local changed = {}
  for key, value in pairs(values) do
    if type(value) == "table" then
      if type(previous[key]) ~= "table" then previous[key] = {} end
      local nested = changed_properties(previous[key], value)
      if next(nested) then changed[key] = nested end
    elseif previous[key] ~= value then
      previous[key], changed[key] = value, value
    end
  end
  return changed
end
local function set_changed(item, values)
  rendered[item.name] = rendered[item.name] or {}
  local changed = changed_properties(rendered[item.name], values)
  if next(changed) then item:set(changed) end
end

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
  -- Query order can change with focus and minimization. Window IDs keep icon
  -- positions stable while retaining one icon per Chrome window.
  local ordered_windows = {}
  for index, window in ipairs(windows) do
    ordered_windows[#ordered_windows + 1] = { window = window, order = window.id or index }
  end
  table.sort(ordered_windows, function(a, b) return a.order < b.order end)
  for _, entry in ipairs(ordered_windows) do
    local window = entry.window
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
      set_changed(pill.item, { drawing = visible, display = display or "active", icon = {
        string = label,
        padding_left = #apps == 0 and 12 or 10,
        padding_right = #apps == 0 and 12 or 5,
      } })
      set_changed(pill.bracket, { drawing = visible, display = display or "active" })
      if not pill.present or pill.focused ~= focused then
        sbar.animate("sin", 6, function()
          set_changed(pill.item, { icon = { color = focused and colors.mauve or colors.white,
            font = { size = focused and 18.0 or 14.0 },
          } })
          set_changed(pill.bracket, { background = {
            color = focused and colors.bg2 or colors.bg1,
            border_color = focused and colors.mauve or colors.bg2,
            height = focused and 36 or 30, corner_radius = focused and 11 or 9,
          } })
        end)
      end
      pill.present, pill.focused = true, focused
      set_changed(pill.trail, { drawing = visible and #apps > 0, display = display or "active" })
      set_changed(pill.padding, { drawing = visible, display = display or "active" })
      for i, slot in ipairs(pill.slots) do
        local app = (apps_by_space[space.index] or {})[i]
        set_changed(slot, { drawing = visible and app ~= nil, display = display or "active",
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
      pill.present = false
      set_changed(pill.item, { drawing = visible, display = display or "active", icon = {
        string = tostring(index), color = colors.grey or colors.white,
        font = { size = 14.0 }, padding_left = 12, padding_right = 12,
      } })
      set_changed(pill.bracket, { drawing = visible, display = display or "active", background = {
        color = colors.bg1, border_color = colors.bg2, height = 30, corner_radius = 9,
      } })
      set_changed(pill.trail, { drawing = false })
      set_changed(pill.padding, { drawing = visible, display = display or "active" })
      for _, slot in ipairs(pill.slots) do set_changed(slot, { drawing = false }) end
    end
  end
end

local function remaining_windows(windows, prune)
  local remaining, seen = {}, {}
  for _, window in ipairs(windows) do
    if window.id then seen[window.id] = true end
    if not removed_windows[window.id] then remaining[#remaining + 1] = window end
  end
  if prune then
    for id in pairs(removed_windows) do
      if not seen[id] then removed_windows[id] = nil end
    end
  end
  return remaining
end

local update
local function labels_ready(spaces, layout)
  -- During daemon startup and profile changes, managed desktops temporarily
  -- lose their labels. Keep the previous frame until spaces.sh finishes;
  -- otherwise these desktops create duplicate D pills beside the fixed slots.
  for _, screen in ipairs(layout or {}) do
    local managed = {}
    for _, space in ipairs(spaces) do
      local label = space.label or ""
      if space.display == screen.index and not space["is-native-fullscreen"]
        and (label == "" or label:match("^ws[1-9]$")) then
        managed[#managed + 1] = space
      end
    end
    table.sort(managed, function(a, b) return a.index < b.index end)
    for i, workspace in ipairs(screen.workspaces or {}) do
      if managed[i] and managed[i].label ~= "ws" .. workspace then return false end
    end
  end
  return true
end

update = function()
  if busy then pending = true; return end
  busy = true
  retry_token = retry_token + 1
  local token = retry_token
  local epoch = topology_epoch
  local windows_at_start = window_epoch
  local refresh_topology = topology == nil
  -- Combine JSON once, and let SbarLua decode it. A failed query leaves the
  -- last complete frame visible instead of clearing the bar during a hotplug.
  local command = prefix .. [[
    spaces=$(yabai -m query --spaces) &&
    windows=$(yabai -m query --windows) &&
  ]]
  if refresh_topology then
    command = command .. [[
    displays=$(yabai -m query --displays) &&
    bar_displays=$(sketchybar --query displays) &&
    layout=$(cat "$HOME/.local/state/dotfiles-wm/display-layout.json" 2>/dev/null || echo '[]') &&
    jq -n --argjson spaces "$spaces" --argjson windows "$windows" \
      --argjson displays "$displays" --argjson bar_displays "$bar_displays" --argjson layout "$layout" \
      '{spaces:$spaces, windows:$windows, displays:$displays, bar_displays:$bar_displays, layout:$layout}'
  ]]
  else
    command = command .. [[
      printf '{"spaces":%s,"windows":%s}\n' "$spaces" "$windows"
    ]]
  end
  sbar.exec(command, function(result)
    local valid = false
    if epoch == topology_epoch and type(result) == "table"
      and type(result.spaces) == "table" and #result.spaces > 0
      and type(result.windows) == "table" then
      if refresh_topology and type(result.displays) == "table"
        and #result.displays > 0 and type(result.bar_displays) == "table"
        and #result.bar_displays > 0 then
        topology = { displays = result.displays, bar_displays = result.bar_displays,
          layout = result.layout }
      end
      if topology and labels_ready(result.spaces, topology.layout) then
        local windows = remaining_windows(result.windows, windows_at_start == window_epoch)
        last_snapshot = { spaces = result.spaces, windows = windows }
        render(result.spaces, windows, topology.displays, topology.bar_displays, topology.layout)
        valid = true
      end
    end
    busy = false
    if valid then retry_count = 0 end
    if pending then
      pending = false
      update()
    elseif not valid and retry_count < #retry_delays then
      retry_count = retry_count + 1
      sbar.delay(retry_delays[retry_count], function()
        -- A newer query supersedes this timer. There is no idle polling.
        if token == retry_token then update() end
      end)
    end
  end)
end
local observer = sbar.add("item", "yabai.observer", { drawing = false, updates = true })
local function requested_update()
  retry_count = 0
  update()
end
observer:subscribe({ "space_change", "space_windows_change",
  "yabai_windows_changed" }, function(env)
  local event = env.EVENT or env.SENDER
  local id, pid = tonumber(env.WINDOW_ID), tonumber(env.PROCESS_ID)
  if event == "window_created" and id then removed_windows[id] = nil end
  if event == "window_destroyed" and id then removed_windows[id] = true end
  if event == "application_terminated" and pid and last_snapshot then
    for _, window in ipairs(last_snapshot.windows) do
      if window.pid == pid and window.id then removed_windows[window.id] = true end
    end
  end
  if event == "window_destroyed" or event == "application_terminated"
    or event == "space_windows_change" then
    window_epoch = window_epoch + 1
    if topology and last_snapshot then
      last_snapshot.windows = remaining_windows(last_snapshot.windows, false)
      render(last_snapshot.spaces, last_snapshot.windows,
        topology.displays, topology.bar_displays, topology.layout)
    end
    -- CoreGraphics can list a closing window during its exit animation. Recheck
    -- once after the burst; never wait for the user to change Space or focus.
    settle_token = settle_token + 1
    local token = settle_token
    sbar.delay(0.12, function()
      if token == settle_token then requested_update() end
    end)
  end
  requested_update()
end)
observer:subscribe({ "display_change", "system_woke" }, function()
  topology_epoch = topology_epoch + 1
  topology = nil
  requested_update()
end)
update()
