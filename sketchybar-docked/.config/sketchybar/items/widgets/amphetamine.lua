local colors = require("colors")

local alias_name = "Amphetamine,Amphetamine"
local hovered, busy, status_pending = false, false, false
local revision = 0
local hover_pending, watch_pending = false, false
local hover_revision = 0
local check_hover
local watch_pointer
local suppress_hover = false

local amphetamine = sbar.add("alias", alias_name, {
  position = "right",
  width = "dynamic",
  alias = { scale = 1.0, color = colors.grey, update_freq = 2 },
  update_freq = 1,
  icon = { drawing = false },
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
    align = "center",
    height = 28,
    background = {
      color = colors.popup.bg,
      border_color = colors.bg2,
      border_width = 1,
      corner_radius = 9,
    },
  },
})

local function tooltip_row(id, text)
  return sbar.add("item", "amphetamine." .. id, {
    position = "popup." .. alias_name,
    width = 290,
    icon = { drawing = false },
    label = { string = text, padding_left = 12, padding_right = 12, color = colors.grey },
  })
end

local remaining = tooltip_row("remaining", "Checking session…")
local hint = tooltip_row("hint", "Right-click for Amphetamine menu")

local function run_script(action, callback)
  sbar.exec('/usr/bin/python3 "$CONFIG_DIR/helpers/amphetamine.py" ' .. action, callback)
end

local function show_status(result, exit_code)
  if exit_code ~= 0 then
    remaining:set({ label = { string = "Could not read Amphetamine", color = colors.red } })
    hint:set({ label = { string = "Right-click to check the native menu" } })
    return
  end
  if type(result) ~= "table" then return end
  local seconds = result.seconds
  local automatic = result.automatic
  if type(seconds) ~= "number" then return end

  local active = seconds ~= -3
  local text
  if seconds > 0 then
    text = string.format("%dh %02dm %02ds remaining",
      math.floor(seconds / 3600), math.floor(seconds % 3600 / 60), seconds % 60)
  elseif seconds == 0 then
    text = "Active · no time limit"
  elseif seconds == -1 then
    text = "Active · automatic trigger"
  elseif seconds == -2 then
    text = "Active · app or scheduled session"
  else
    text = "Off · click to start default duration"
  end

  local help = "Click to stop · right-click for menu"
  if not active then
    if result.paused_until_reconnect then
      help = "Automatic resumes after unplug + plug in"
    elseif automatic then
      help = "Auto enabled · right-click for menu"
    else
      help = "Auto disabled · right-click for menu"
    end
  end
  local color = active and colors.green or colors.grey
  amphetamine:set({ alias = { color = color } })
  remaining:set({ label = { string = text, color = color } })
  hint:set({ label = { string = help, color = colors.grey } })
end

local function refresh_tooltip()
  if not hovered or busy or status_pending then return end
  status_pending = true
  local requested_revision = revision
  run_script("status", function(result, exit_code)
    status_pending = false
    if requested_revision == revision and not busy then show_status(result, exit_code) end
  end)
end

local function update_status()
  if check_hover then check_hover() end
  -- Keep the bar accurate without querying AppleScript when the tooltip is closed.
  local requested_revision = revision
  sbar.exec("/usr/bin/pmset -g assertions", function(result, exit_code)
    if exit_code ~= 0 or busy or requested_revision ~= revision then return end
    local active = false
    for line in result:gmatch("[^\r\n]+") do
      if line:find("(Amphetamine)", 1, true)
          and line:find("PreventUserIdleSystemSleep", 1, true) then
        active = true
        break
      end
    end
    amphetamine:set({ alias = { color = active and colors.green or colors.grey } })
    refresh_tooltip()
  end)
end

amphetamine:subscribe("mouse.clicked", function(env)
  if env.BUTTON == "right" then
    hovered = false
    hover_revision = hover_revision + 1
    suppress_hover = true
    amphetamine:set({ popup = { drawing = false } })
    watch_pointer()
    sbar.exec('"$CONFIG_DIR/helpers/menus/bin/menus" -s "Amphetamine,Amphetamine"')
    return
  end
  if env.BUTTON ~= "left" or busy then return end
  busy = true
  revision = revision + 1
  remaining:set({ label = { string = "Updating session…", color = colors.white } })
  run_script("toggle", function(result, exit_code)
    busy = false
    show_status(result, exit_code)
  end)
end)

local function hide_tooltip()
  hovered = false
  hover_revision = hover_revision + 1
  amphetamine:set({ popup = { drawing = false } })
end

watch_pointer = function()
  if (not hovered and not suppress_hover) or watch_pending then return end
  watch_pending = true
  run_script("hover-watch", function(result, exit_code)
    watch_pending = false
    if not hovered and not suppress_hover then return end
    if exit_code ~= 0 or type(result) ~= "table" or not result.inside then
      suppress_hover = false
      hide_tooltip()
    else
      watch_pointer()
    end
  end)
end

check_hover = function()
  if hovered or hover_pending or suppress_hover then return end
  hover_pending = true
  local requested_revision = hover_revision
  run_script("hover-check", function(result, exit_code)
    hover_pending = false
    if requested_revision ~= hover_revision then return end
    if exit_code ~= 0 or type(result) ~= "table" or not result.inside then return end
    hovered = true
    amphetamine:set({ popup = { drawing = true } })
    refresh_tooltip()
    watch_pointer()
  end)
end
-- Alias items can miss entry events and emit exit events during image refreshes.
-- Check direct entry on the routine tick; the pointer watcher handles real exits.
amphetamine:subscribe("mouse.entered", check_hover)
local function sync_power(env)
  local action = "sync"
  if env and (env.INFO == "AC" or env.INFO == "BATTERY") then
    action = action .. " " .. env.INFO
  end
  run_script(action, function(_, exit_code)
    if exit_code == 0 then update_status() end
  end)
end
amphetamine:subscribe("power_source_change", sync_power)
amphetamine:subscribe("system_woke", sync_power)
amphetamine:subscribe({ "routine", "forced" }, update_status)
sync_power()
