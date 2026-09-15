-- Headless SketchyBar event/render checks; no live commands are executed.
local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function()
  return { mauve=1, white=2, transparent=0, bg1=3, bg2=4, grey=5 }
end
package.preload.settings = function() return { font={numbers="Test"} } end
local items, callbacks, commands, events = {}, {}, {}, {}
local function merge(target, values)
  for key, value in pairs(values) do
    if type(value) == "table" then
      if type(target[key]) ~= "table" then target[key] = {} end
      merge(target[key], value)
    else target[key] = value end
  end
end
sbar = {
  animate = function(_, _, callback) callback() end,
  add = function(kind, name, props, bracket_props)
    if kind == "event" then return end
    local item = { name=name, props=bracket_props or props or {} }
    function item:set(values) merge(self.props, values) end
    function item:subscribe(event, callback)
      if type(event) ~= "table" then event = {event} end
      for _, value in ipairs(event) do events[name .. ":" .. value] = callback end
    end
    items[name] = item
    return item
  end,
  exec = function(command, callback)
    commands[#commands+1] = command
    if callback then callbacks[#callbacks+1] = callback end
  end,
}
dofile(root .. "/yabai/.config/yabai/sketchybar.lua")
assert(#callbacks == 1)
for i=1,6 do assert(items["yabai.space." .. i], "Reserve all slots before the query returns") end
local function fixture()
  return {
    spaces = {
      {index=1,display=1,label="ws3",["has-focus"]=true,["is-native-fullscreen"]=false},
      {index=2,display=2,label="ws2",["has-focus"]=false,["is-native-fullscreen"]=false},
      {index=3,display=2,label="",["is-native-fullscreen"]=true},
    },
    windows = {{space=1,app="Terminal"},{space=1,app="Terminal"},
      {space=1,app="Google Chrome"},{space=1,app="Google Chrome"},
      {space=1,app="Google Chrome",["is-hidden"]=true}},
    displays = {{index=1,id=100,frame={x=0,y=0}},{index=2,id=200,frame={x=1920,y=0}}},
    bar_displays = {{DirectDisplayID=100,["arrangement-id"]=2},{DirectDisplayID=200,["arrangement-id"]=1}},
  }
end
callbacks[1](fixture())
assert(items["yabai.space.3"].props.display == 2, "Must join physical IDs, not indices")
assert(items["yabai.space.3"].props.icon.string == "3")
assert(items["yabai.space.3.app.1"].props.background.image == "app.Terminal")
assert(items["yabai.space.3.app.2"].props.background.image == "app.Google Chrome")
assert(items["yabai.space.3.app.3"].props.background.image == "app.Google Chrome")
assert(items["yabai.space.3.app.3"].props.drawing == true, "Show each Chrome window")
assert(items["yabai.space.3.app.4"].props.drawing == false, "Group other apps and skip hidden windows")
assert(items["yabai.space.native3"] == nil, "Skip native fullscreen Spaces")
for _, i in ipairs({1,4,5,6}) do
  local props = items["yabai.space." .. i].props
  assert(props.drawing == true, "Missing desktop slots stay visible")
  assert(props.icon.color == 5, "Missing desktops are dimmed")
  assert(props.display == (i % 2 == 0 and 1 or 2), "Odd/even display mapping")
end
events["yabai.space.5:mouse.clicked"]({BUTTON="left"})
assert(commands[#commands]:match("ensure%-spaces.sh"), "Missing desktop retries setup")
events["yabai.space.3:mouse.clicked"]({BUTTON="left"})
assert(commands[#commands]:match("focus%-space.py.* 1$"), "Click must use native index, not label digit")
events["yabai.mode:yabai_mode_changed"]({MODE="resize"})
assert(items["yabai.mode"].props.label.string == "resize")
assert(items["yabai.mode"].props.drawing == true)
events["yabai.mode:yabai_mode_changed"]({MODE="default"})
assert(items["yabai.mode"].props.drawing == false)

events["yabai.observer:display_change"]({})
events["yabai.observer:yabai_windows_changed"]({})
assert(#callbacks == 2, "Overlapping requests must be coalesced")
local data = fixture()
data.spaces = {data.spaces[2]}
callbacks[2](data)
assert(#callbacks == 3, "A pending change must get a fresh query")
assert(items["yabai.space.3"].props.drawing == true)
assert(items["yabai.space.3"].props.icon.color == 5)
assert(items["yabai.space.3.app.1"].props.drawing == false)
callbacks[3]("")
assert(items["yabai.space.2"].props.drawing == true, "Query failure should preserve last frame")
events["yabai.observer:display_change"]({})
local laptop = fixture()
laptop.displays = {laptop.displays[1]}
laptop.spaces = {laptop.spaces[1], {index=7, display=1,label="",["is-native-fullscreen"]=false}}
callbacks[4](laptop)
for i=1,6 do assert(items["yabai.space." .. i].props.display == 2) end
assert(items["yabai.space.native7"].props.drawing == true)
events["yabai.observer:space_change"]({})
laptop.spaces = {laptop.spaces[1]}
callbacks[5](laptop)
assert(items["yabai.space.native7"].props.drawing == false, "Removed extra desktop disappears")
events["yabai.observer:display_change"]({})
local triple = fixture()
triple.displays[#triple.displays+1] = {index=3,id=300,frame={x=-1920,y=0}}
triple.bar_displays[#triple.bar_displays+1] = {DirectDisplayID=300,["arrangement-id"]=3}
triple.layout = {{id=100,workspaces={2,4,6}},{id=200,workspaces={1,3,5}},{id=300,workspaces={7,8,9}}}
triple.spaces = {{index=1,display=3,label="ws7",["has-focus"]=true,["is-native-fullscreen"]=false}}
callbacks[6](triple)
for _, i in ipairs({7,8,9}) do
  assert(items["yabai.space." .. i].props.drawing == true)
  assert(items["yabai.space." .. i].props.display == 3, "Laptop gets three additional slots")
end
assert(items["yabai.space.1"].props.display == 1, "Missing slots follow plan, not left-right fallback")
events["yabai.observer:display_change"]({})
callbacks[7](fixture())
for i=7,9 do assert(items["yabai.space." .. i].props.drawing == false) end
print("SketchyBar rendering, persistent slots, display mapping, clicks, and event coalescing passed")
