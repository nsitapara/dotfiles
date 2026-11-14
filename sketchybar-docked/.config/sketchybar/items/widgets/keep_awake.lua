local colors = require("colors")

-- The coffee cup: green while the Mac is kept from idle-sleeping, grey when it
-- may sleep. The native keep_awake provider (helpers/event_providers/keep_awake)
-- holds the power assertion itself, so the Amphetamine app is not needed. Left
-- alone it keeps the Mac awake on the power adapter and lets it sleep on
-- battery. A click opens a menu that overrides that until the chosen time ends
-- or the power source changes. The widget runs no timer while the menu is closed.
local bin = "$CONFIG_DIR/helpers/event_providers/keep_awake/bin/keep_awake"
local popup_width = 250
local state = { awake = false, mode = "auto", power = "AC", ends = 0 }
local open = false

sbar.add("event", "keep_awake")
sbar.exec("killall keep_awake >/dev/null 2>&1; exec " .. bin .. " daemon keep_awake")

local keep_awake = sbar.add("item", "widgets.keep_awake", {
  position = "right",
  width = "dynamic",
  update_freq = 0,
  icon = { string = "􀸙", color = colors.grey, padding_left = 8, padding_right = 8 },
  label = { drawing = false },
  padding_left = 5,
  padding_right = 0,
  background = {
    drawing = true,
    color = colors.bg1,
    border_color = colors.bg2,
    border_width = 2,
    height = 28,
    corner_radius = 9,
  },
  popup = {
    -- The cup sits near the screen edge; a centred menu would run off it.
    align = "right",
    height = 28,
    background = {
      color = colors.popup.bg,
      border_color = colors.bg2,
      border_width = 1,
      corner_radius = 9,
    },
  },
})

local function row(id, text)
  return sbar.add("item", "keep_awake." .. id, {
    position = "popup." .. keep_awake.name,
    width = popup_width,
    icon = { drawing = false },
    label = { string = text, padding_left = 12, padding_right = 12, color = colors.white },
    background = { drawing = false, color = colors.bg2, height = 24, corner_radius = 6 },
  })
end

local status = row("status", "Checking…")
local actions = {
  { id = "30m", text = "Keep awake for 30 minutes", command = "set on 1800" },
  { id = "1h", text = "Keep awake for 1 hour", command = "set on 3600" },
  { id = "2h", text = "Keep awake for 2 hours", command = "set on 7200" },
  { id = "unlimited", text = "Keep awake, no time limit", command = "set on" },
  { id = "custom", text = "Custom time…", command = "custom" },
  { id = "off", text = "Turn off", command = "set off",
    shown = function() return state.awake end },
  -- On battery, "Turn off" already returns a timed session to automatic.
  { id = "auto", text = "Back to automatic", command = "set auto",
    shown = function() return state.mode == "off" or (state.mode == "on" and state.power == "AC") end },
}

local function status_text()
  if state.mode == "on" and state.ends > 0 then
    local left = math.max(state.ends - os.time(), 0)
    return string.format("Awake · %dh %02dm %02ds left",
      math.floor(left / 3600), math.floor(left % 3600 / 60), left % 60)
  end
  if state.mode == "on" then return "Awake · no time limit" end
  if state.mode == "off" then return "Off · until the next plug-in" end
  if state.awake then return "Awake · plugged in" end
  return "Off · on battery"
end

local function render()
  local color = state.awake and colors.green or colors.grey
  keep_awake:set({ icon = { color = color } })
  status:set({ label = { string = status_text(), color = color } })
  for _, action in ipairs(actions) do
    action.item:set({ drawing = not action.shown or action.shown() })
  end
end

-- Takes the provider's event (text fields) and its "status" JSON alike.
local function apply(values)
  if type(values) ~= "table" or not values.mode then return end
  state.awake = tonumber(values.awake) == 1
  state.mode = values.mode
  state.power = values.power
  state.ends = tonumber(values.ends) or 0
  render()
end

-- The countdown only ticks while the menu is open.
local function set_open(value)
  open = value
  keep_awake:set({ popup = { drawing = open }, update_freq = open and 1 or 0 })
  if open then render() end
end

for _, action in ipairs(actions) do
  action.item = row(action.id, action.text)
  action.item:subscribe("mouse.entered", function()
    action.item:set({ background = { drawing = true } })
  end)
  action.item:subscribe("mouse.exited", function()
    action.item:set({ background = { drawing = false } })
  end)
  action.item:subscribe("mouse.clicked", function()
    action.item:set({ background = { drawing = false } })
    set_open(false)
    sbar.exec(bin .. " " .. action.command)
  end)
end

keep_awake:subscribe("keep_awake", apply)
keep_awake:subscribe("routine", render)
keep_awake:subscribe("mouse.clicked", function() set_open(not open) end)
keep_awake:subscribe("mouse.exited.global", function() set_open(false) end)
-- The provider also hears power changes from macOS; these cover wake and a
-- notification it missed.
keep_awake:subscribe({ "power_source_change", "system_woke" }, function()
  sbar.exec(bin .. " sync")
end)
-- The provider reports changes only, and its first report can arrive before
-- the subscription above exists.
sbar.exec(bin .. " status", apply)
