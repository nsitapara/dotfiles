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
  position = "left",
  icon = { string = "Y", color = colors.mauve },
  label = { string = "", drawing = false },
})
mode:subscribe("yabai_mode_changed", function(env)
  local value = env.MODE or "default"
  mode:set({ label = { string = value, drawing = value ~= "default" } })
end)

local function create_pill(index)
  local item = sbar.add("item", "yabai.space." .. index, {
    position = "left",
    icon = {
      font = { family = settings.font.numbers, size = 14.0 },
      padding_left = 10, padding_right = 10,
    },
    label = { drawing = false },
    background = { drawing = false },
    padding_left = 2, padding_right = 2,
  })
  local pill = { item = item, slots = {}, index = index }
  local members = { item.name }
  local function clicked()
    -- The index comes from yabai's numeric JSON, never from an app title.
    sbar.exec(prefix .. "yabai -m space --focus " .. pill.index)
  end
  item:subscribe("mouse.clicked", clicked)
  for slot_index = 1, 5 do
    local slot = sbar.add("item", "yabai.space." .. index .. ".app." .. slot_index, {
      position = "left", drawing = false, width = 29,
      padding_left = 0, padding_right = 0,
      icon = { drawing = false }, label = { drawing = false },
      background = {
        drawing = true, color = colors.transparent, height = 24,
        image = { drawing = true, scale = 0.7, corner_radius = 5 },
      },
    })
    slot:subscribe("mouse.clicked", clicked)
    pill.slots[slot_index] = slot
    members[#members + 1] = slot.name
  end
  pill.bracket = sbar.add("bracket", "yabai.space." .. index .. ".bracket", members, {
    background = { color = colors.bg1, border_color = colors.bg2,
      border_width = 2, height = 30, corner_radius = 9 },
  })
  pills[index] = pill
  return pill
end

local function render(spaces, windows, displays, bar_displays)
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
  local apps_by_space, seen_apps = {}, {}
  for _, window in ipairs(windows) do
    local id, app = window.space, window.app
    apps_by_space[id] = apps_by_space[id] or {}
    seen_apps[id] = seen_apps[id] or {}
    if app and app ~= "" and not seen_apps[id][app] and not window["is-hidden"] then
      seen_apps[id][app] = true
      table.insert(apps_by_space[id], app)
    end
  end
  local seen = {}
  for _, space in ipairs(spaces) do
    if not space["is-native-fullscreen"] and type(space.index) == "number" then
      seen[space.index] = true
      local pill = pills[space.index] or create_pill(space.index)
      local display = display_map[space.display]
      local visible = display ~= nil
      local focused = space["has-focus"]
      local label = (space.label or ""):match("^ws([1-6])$") or tostring(space.index)
      pill.item:set({ drawing = visible, display = display or "active", icon = {
        string = label, color = focused and colors.mauve or colors.white,
        font = { size = focused and 18.0 or 14.0 },
      } })
      pill.bracket:set({ drawing = visible, display = display or "active", background = {
        color = focused and colors.bg2 or colors.bg1,
        border_color = focused and colors.mauve or colors.bg2,
        height = focused and 36 or 30, corner_radius = focused and 11 or 9,
      } })
      for i, slot in ipairs(pill.slots) do
        local app = (apps_by_space[space.index] or {})[i]
        slot:set({ drawing = visible and app ~= nil, display = display or "active",
          background = { image = app and ("app." .. app) or "" } })
      end
    end
  end
  for index, pill in pairs(pills) do
    if not seen[index] then
      pill.item:set({ drawing = false })
      pill.bracket:set({ drawing = false })
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
    jq -n --argjson spaces "$spaces" --argjson windows "$windows" \
      --argjson displays "$displays" --argjson bar_displays "$bar_displays" \
      '{spaces:$spaces, windows:$windows, displays:$displays, bar_displays:$bar_displays}'
  ]]
  sbar.exec(command, function(result)
    if type(result) == "table" and type(result.spaces) == "table"
      and type(result.windows) == "table" and type(result.displays) == "table"
      and type(result.bar_displays) == "table" then
      render(result.spaces, result.windows, result.displays, result.bar_displays)
    end
    busy = false
    if pending then pending = false; update() end
  end)
end
local observer = sbar.add("item", "yabai.observer", { drawing = false, updates = true })
observer:subscribe({ "space_change", "space_windows_change", "display_change",
  "system_woke", "yabai_windows_changed" }, update)
update()
