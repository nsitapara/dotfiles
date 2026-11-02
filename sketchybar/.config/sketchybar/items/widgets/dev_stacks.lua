-- web-platform's native dev stacks run detached from every terminal, so Pilot
-- only shows them as a port count. The bar shows how many run (orange when one
-- has sat idle past the limit); the popup lists each and stops one on click.
local colors = require("colors")

local name = "widgets.dev_stacks"
local cli = '"$HOME/.local/bin/dev-stacks"'
local max_rows = 15
local pending, stopping, dirty = false, false, false
local paths, states = {}, {}
-- Paths a click is stopping; their rows say so until the stack is gone.
local stopping_paths = {}
local poll_freq, idle_freq = 2, 60

local stacks = sbar.add("item", name, {
  position = "right",
  drawing = false,
  -- Hidden items get no routine updates by default; keep polling at zero.
  updates = "on",
  update_freq = idle_freq,
  icon = { string = "⛁", color = colors.grey, padding_left = 8, padding_right = 4 },
  label = { string = "0", padding_right = 8 },
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
    align = "right",
    background = {
      color = colors.popup.bg,
      border_color = colors.bg2,
      border_width = 1,
      corner_radius = 9,
    },
  },
})

local function popup_row(id, drawing)
  return sbar.add("item", name .. "." .. id, {
    position = "popup." .. name,
    drawing = drawing,
    icon = { drawing = false },
    label = { string = "", color = colors.grey, padding_left = 12, padding_right = 12 },
  })
end

local header = popup_row("header", true)
local rows = {}
for i = 1, max_rows do rows[i] = popup_row("row." .. i, false) end
local sweep = popup_row("sweep", true)

local status_text = { idle = "", busy = " · in use", active = " · active" }
local status_color = { idle = colors.orange, busy = colors.green, active = colors.white }

local function render(result)
  local list, idle = result.stacks, 0
  for _, stack in ipairs(list) do
    if stack.state == "idle" then idle = idle + 1 end
  end
  local hours = string.format("%g", result.hours or 6)
  stacks:set({
    drawing = #list > 0,
    icon = { color = idle > 0 and colors.orange or colors.grey },
    label = { string = tostring(#list) },
  })
  if #list == 0 then stacks:set({ popup = { drawing = false } }) end
  header:set({ label = { string = #list .. " native dev stacks · click one to stop it" } })
  paths, states = {}, {}
  for i, row in ipairs(rows) do
    local stack = list[i]
    if stack then
      paths[i], states[i] = stack.path, stack.state
      local status = stopping_paths[stack.path] and " · stopping…" or status_text[stack.state] or ""
      row:set({
        drawing = true,
        label = {
          string = string.format("%s · idle %s%s", stack.label, stack.idle, status),
          color = stopping_paths[stack.path] and colors.white or status_color[stack.state] or colors.grey,
        },
      })
    else
      row:set({ drawing = false })
    end
  end
  if stopping then
    sweep:set({ label = { string = "Stopping…", color = colors.white } })
    return
  end
  sweep:set({ label = {
    string = idle > 0 and string.format("Stop the %d idle %sh+", idle, hours) or ("Nothing idle " .. hours .. "h+"),
    color = idle > 0 and colors.orange or colors.grey,
  } })
end

local refresh
refresh = function()
  -- Never overlap two lists, but don't drop the ask either: a stop that
  -- finishes mid-list must still be seen.
  if pending then dirty = true; return end
  pending, dirty = true, false
  sbar.exec(cli .. " list --json", function(result, exit_code)
    pending = false
    if exit_code ~= 0 or type(result) ~= "table" or type(result.stacks) ~= "table" then
      stacks:set({ drawing = true, icon = { color = colors.red }, label = { string = "?" } })
      header:set({ label = { string = "dev-stacks failed; run it in a terminal" } })
    else
      render(result)
    end
    if dirty then refresh() end
  end)
end

-- A stop takes seconds per stack; poll meanwhile so rows drop out as they stop.
local function run(command, targets)
  if stopping then return end
  stopping = true
  for _, path in ipairs(targets) do stopping_paths[path] = true end
  stacks:set({ update_freq = poll_freq })
  refresh()
  sbar.exec(command, function()
    stopping = false
    stopping_paths = {}
    stacks:set({ update_freq = idle_freq })
    refresh()
  end)
end

for i, row in ipairs(rows) do
  row:subscribe("mouse.clicked", function()
    local path = paths[i]
    if path then run(cli .. ' stop --force "' .. path .. '"', { path }) end
  end)
end
sweep:subscribe("mouse.clicked", function()
  local targets = {}
  for i, path in pairs(paths) do
    if states[i] == "idle" then targets[#targets + 1] = path end
  end
  run(cli .. " stop-idle", targets)
end)

stacks:subscribe("mouse.clicked", function()
  stacks:set({ popup = { drawing = "toggle" } })
  refresh()
end)
stacks:subscribe("mouse.exited.global", function()
  stacks:set({ popup = { drawing = false } })
end)
stacks:subscribe({ "routine", "forced", "system_woke" }, refresh)
refresh()
