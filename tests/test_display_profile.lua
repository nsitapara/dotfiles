-- Headless checks for the display profile menu; no live commands run.
local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function() return { mauve=1, white=2, grey=3, bg1=4 } end
for _, profile in ipairs({"sketchybar", "sketchybar-docked"}) do
  local items, events, callbacks, commands = {}, {}, {}, {}
  sbar = {
    add = function(kind, name, props)
      if kind == "event" then return end
      local item = { name=name, props=props }
      function item:set(values)
        for k, v in pairs(values) do
          if type(v) == "table" and type(self.props[k]) == "table" then
            for kk, vv in pairs(v) do self.props[k][kk] = vv end
          else self.props[k] = v end
        end
      end
      function item:subscribe(names, callback)
        if type(names) == "string" then names = {names} end
        for _, event in ipairs(names) do events[name .. ":" .. event] = callback end
      end
      items[name] = item
      return item
    end,
    exec = function(command, callback)
      commands[#commands+1] = command
      if callback then callbacks[#callbacks+1] = callback end
    end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/display_profile.lua")
  local menu = assert(items["display.profile"], "menu item exists")
  assert(menu.props.position == "right")
  assert(#callbacks == 1, "one status query at load")
  callbacks[1]("docked laptop\n") -- pinned docked, but only the laptop layout fit
  assert(menu.props.label.string == "2 MON", menu.props.label.string)
  assert(menu.props.label.color == 3, "a pin that is not in effect shows grey")
  callbacks[1]("docked docked\n")
  assert(menu.props.label.color == 1, "a pin in effect shows the accent color")
  callbacks[1]("auto single\n")
  assert(menu.props.label.string == "AUTO")
  local row = assert(items["display.profile.laptop"], "menu row exists")
  assert(row.props.position == "popup.display.profile")
  assert(items["display.profile.auto"].props.label.color == 1, "active row highlighted")
  assert(items["display.profile.docked"].props.label.color == 2, "inactive row plain")
  events["display.profile:mouse.clicked"]()
  assert(menu.props.popup.drawing == true, "click opens the menu")
  events["display.profile.laptop:mouse.clicked"]()
  assert(commands[#commands]:find('wm.sh" profile laptop', 1, true), commands[#commands])
  assert(menu.props.popup.drawing == false, "choosing a row closes the menu")
end
print("Display profile menu checks passed for both profiles")
