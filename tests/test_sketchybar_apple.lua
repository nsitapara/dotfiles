local root = assert(arg[1])
package.preload.colors = function() return {transparent=0} end
for _, profile in ipairs({"sketchybar", "sketchybar-docked"}) do
  local events, commands = {}, {}
  sbar = {
    add = function(_, name)
      return {set=function() end, subscribe=function(_, event, callback)
        if name == "front_app.icon" then events[event] = callback end
      end}
    end,
    exec = function(command) commands[#commands+1] = command end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/apple.lua")
  assert(events["mouse.clicked"], "Corner icon must open the native Apple menu")
  local before = #commands
  events["mouse.clicked"]({BUTTON="right"})
  assert(#commands == before, "Only a left click opens the Apple menu")
  events["mouse.clicked"]({BUTTON="left"})
  assert(commands[#commands]:find("sketchybar%-hover/run.py") and
         commands[#commands]:find("%-%-apple%-menu"), "Use the helper's explicit menu handoff")
end
print("Both profiles open the Apple menu from the corner icon")
