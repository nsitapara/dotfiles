-- Headless SketchyBar event/render checks; no live commands are executed.
local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function()
  return { mauve=1, white=2, transparent=0, bg1=3, bg2=4 }
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
local function fixture()
  return {
    spaces = {
      {index=1,display=1,label="ws3",["has-focus"]=true,["is-native-fullscreen"]=false},
      {index=2,display=2,label="ws2",["has-focus"]=false,["is-native-fullscreen"]=false},
      {index=3,display=2,label="",["is-native-fullscreen"]=true},
    },
    windows = {{space=1,app="Terminal"},{space=1,app="Terminal"},{space=1,app="Browser"}},
    displays = {{index=1,id=100},{index=2,id=200}},
    bar_displays = {{DirectDisplayID=100,["arrangement-id"]=2},{DirectDisplayID=200,["arrangement-id"]=1}},
  }
end
callbacks[1](fixture())
assert(items["yabai.space.1"].props.display == 2, "Must join physical IDs, not indices")
assert(items["yabai.space.1"].props.icon.string == "3")
assert(items["yabai.space.1.app.1"].props.background.image == "app.Terminal")
assert(items["yabai.space.1.app.2"].props.background.image == "app.Browser")
assert(items["yabai.space.1.app.3"].props.drawing == false, "Deduplicate icons")
assert(items["yabai.space.3"] == nil, "Skip native fullscreen Spaces")
events["yabai.space.1:mouse.clicked"]({BUTTON="left"})
assert(commands[#commands]:match("space %-%-focus 1$"), "Click must use native index, not label digit")
events["yabai.mode:yabai_mode_changed"]({MODE="resize"})
assert(items["yabai.mode"].props.label.string == "resize")
assert(items["yabai.mode"].props.label.drawing == true)

events["yabai.observer:display_change"]({})
events["yabai.observer:yabai_windows_changed"]({})
assert(#callbacks == 2, "Overlapping requests must be coalesced")
local data = fixture()
data.spaces = {data.spaces[2]}
callbacks[2](data)
assert(#callbacks == 3, "A pending change must get a fresh query")
assert(items["yabai.space.1"].props.drawing == false)
assert(items["yabai.space.1.app.1"].props.drawing == false)
callbacks[3]("")
assert(items["yabai.space.2"].props.drawing == true, "Query failure should preserve last frame")
print("SketchyBar rendering, display mapping, clicks, and event coalescing passed")
