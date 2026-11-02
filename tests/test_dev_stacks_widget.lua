-- The dev-stacks widget: hidden at zero, one popup row per stack, and a stop
-- shows progress until the stopped stacks drop out of the list.
local root = assert(arg[1], "Pass repository path")
package.preload.colors = function()
  return { grey = 1, green = 2, red = 3, white = 4, orange = 5, bg1 = 6, bg2 = 7, popup = { bg = 8 } }
end

local function merge(t, v)
  for k, x in pairs(v) do
    if type(x) == "table" then t[k] = t[k] or {}; merge(t[k], x) else t[k] = x end
  end
end

local function stack(label, state)
  return { label = label, path = "/wt/" .. label, idle = "2d 3h", state = state }
end
local three = { hours = 6, stacks = { stack("web-2478", "idle"), stack("web-2486", "busy"), stack("web-2099", "active") } }

for _, profile in ipairs({ "sketchybar", "sketchybar-docked" }) do
  local items, events, commands, callbacks = {}, {}, {}, {}
  sbar = {
    add = function(_, name, props)
      local item = { name = name, props = props }
      function item:set(values) merge(self.props, values) end
      function item:subscribe(event, fn)
        for _, e in ipairs(type(event) == "table" and event or { event }) do events[name .. ":" .. e] = fn end
      end
      items[name] = item
      return item
    end,
    exec = function(command, fn) commands[#commands + 1] = command; callbacks[#callbacks + 1] = fn end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/dev_stacks.lua")
  local widget = items["widgets.dev_stacks"]
  local function row(i) return items["widgets.dev_stacks.row." .. i].props end
  local function answer(result, code) table.remove(callbacks, 1)(result, code or 0) end
  local function check(ok, what) assert(ok, profile .. ": " .. what) end

  check(widget.props.updates == "on", "a hidden widget must keep polling")
  check(#commands == 1 and commands[1]:find("list %-%-json"), "loads by listing stacks")
  events["widgets.dev_stacks:routine"]()
  check(#commands == 1, "a pending list must not overlap another")
  answer({ hours = 6, stacks = {} })
  check(widget.props.drawing == false, "hidden when nothing runs")
  check(#commands == 2, "a refresh asked for mid-list runs once the list returns")

  answer(three)
  check(widget.props.drawing == true and widget.props.label.string == "3", "shows the count")
  check(widget.props.icon.color == 5, "orange while a stack is idle")
  check(row(3).drawing == true and row(4).drawing == false, "one row per stack, spare rows hidden")
  check(row(2).label.string == "web-2486 · idle 2d 3h · in use", "row text")
  check(items["widgets.dev_stacks.sweep"].props.label.string == "Stop the 1 idle 6h+", "sweep row")

  events["widgets.dev_stacks.sweep:mouse.clicked"]()
  check(commands[#commands] == '"$HOME/.local/bin/dev-stacks" stop-idle', "sweep runs stop-idle")
  check(widget.props.update_freq == 2, "polls while stopping")
  answer(three)
  check(row(1).label.string == "web-2478 · idle 2d 3h · stopping…", "the idle row says it is stopping")
  check(row(2).label.string == "web-2486 · idle 2d 3h · in use", "an in-use row is left alone")
  check(items["widgets.dev_stacks.sweep"].props.label.string == "Stopping…", "sweep row shows progress")
  events["widgets.dev_stacks.sweep:mouse.clicked"]()
  check(#callbacks == 1, "a second click doesn't start another stop")

  answer("", 0)
  check(widget.props.update_freq == 60, "back to slow polling after the stop")
  answer({ hours = 6, stacks = { stack("web-2486", "busy"), stack("web-2099", "active") } })
  check(widget.props.label.string == "2" and row(3).drawing == false, "the stopped stack drops out")
  check(items["widgets.dev_stacks.sweep"].props.label.string == "Nothing idle 6h+", "nothing left to sweep")

  events["widgets.dev_stacks.row.1:mouse.clicked"]()
  check(commands[#commands]:find('stop %-%-force "/wt/web%-2486"'), "a row click stops that stack")
  answer({ hours = 6, stacks = {} }, 0)
  answer("", 0)
  answer("", 1)
  check(widget.props.label.string == "?" and widget.props.icon.color == 3, "a failed list shows ?")
end
print("dev_stacks widget tests passed")
