-- Headless SketchyBar event/render checks; no live commands are executed.
local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function()
  return { mauve=1, white=2, transparent=0, bg1=3, bg2=4, grey=5 }
end
package.preload.settings = function() return { font={numbers="Test"} } end
local items, callbacks, commands, events = {}, {}, {}, {}
local set_count, animation_count = 0, 0
local timers = {}
local function merge(target, values)
  for key, value in pairs(values) do
    if type(value) == "table" then
      if type(target[key]) ~= "table" then target[key] = {} end
      merge(target[key], value)
    else target[key] = value end
  end
end
sbar = {
  delay = function(seconds, callback) timers[#timers+1] = {seconds=seconds, callback=callback} end,
  animate = function(_, _, callback) animation_count = animation_count + 1; callback() end,
  add = function(kind, name, props, bracket_props)
    if kind == "event" then return end
    local item = { name=name, props=bracket_props or props or {} }
    function item:set(values) set_count = set_count + 1; merge(self.props, values) end
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
    windows = {{id=1,space=1,app="Terminal"},{id=2,space=1,app="Terminal",["is-floating"]=true},
      {id=3,space=1,app="Google Chrome"},{id=4,space=1,app="Google Chrome",["is-floating"]=true},
      {id=5,space=1,app="Google Chrome",["is-hidden"]=true},
      {id=6,space=1,app="Google Chrome",role="AXHelpTag",["is-floating"]=true},
      {id=7,space=1,app="Finder",["is-minimized"]=true,["split-child"]="none"},
      {id=8,space=1,app="LibreOffice",["split-child"]="none"}},
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
assert(items["yabai.space.3.app.4"].props.background.image == "app.Finder")
assert(items["yabai.space.3.app.4"].props.label.string == "M", "Badge minimized apps")
assert(items["yabai.space.3.app.5"].props.drawing == false,
  "Group other apps; skip hidden windows, tooltips, and closed windows kept alive")
assert(items["yabai.space.3.app.1"].props.label.drawing == false, "Badge an app only when all its windows float")
assert(items["yabai.space.3.app.2"].props.label.drawing == false)
assert(items["yabai.space.3.app.3"].props.label.drawing == true, "Badge a floating Chrome window")
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

events["yabai.observer:yabai_windows_changed"]({})
assert(not commands[#commands]:find("query --displays", 1, true), "Reuse display mappings for window events")
local cached = fixture()
cached.displays, cached.bar_displays = nil, nil
callbacks[8](cached)
assert(items["yabai.space.3"].props.display == 2, "Window-only snapshots use cached mappings")
events["yabai.observer:yabai_windows_changed"]({})
events["yabai.observer:display_change"]({})
callbacks[9](cached)
assert(commands[#commands]:find("query --displays", 1, true), "Hotplug during a query must invalidate its cache")
callbacks[10]("")
events["yabai.observer:yabai_windows_changed"]({})
assert(commands[#commands]:find("query --displays", 1, true), "Failed topology queries must retry")
callbacks[11](fixture())
events["yabai.observer:system_woke"]({})
assert(commands[#commands]:find("query --displays", 1, true), "Wake refreshes topology")
callbacks[12](fixture())
set_count, animation_count = 0, 0
events["yabai.observer:yabai_windows_changed"]({})
callbacks[13](fixture())
assert(set_count == 0 and animation_count == 0, "Identical snapshots must not update or animate items")
events["yabai.observer:space_change"]({})
local focused = fixture()
focused.spaces[1]["has-focus"], focused.spaces[2]["has-focus"] = false, true
callbacks[14](focused)
assert(set_count == 4 and animation_count == 2, "Focus change updates only the two affected pills")
set_count, animation_count = 0, 0
events["yabai.observer:yabai_windows_changed"]({})
focused.windows = {{space=1,app="Terminal"}}
callbacks[15](focused)
assert(set_count == 3 and animation_count == 0, "Only removed app slots should change")

events["yabai.observer:yabai_windows_changed"]({})
callbacks[#callbacks]("[\n")
local count = #callbacks
timers[#timers].callback()
assert(#callbacks == count + 1, "Malformed JSON retries without another event")
local empty = fixture()
empty.windows = {}
callbacks[#callbacks](empty)
assert(items["yabai.space.3.app.1"].props.drawing == false, "Retry removes a closed app without changing spaces")
count = #callbacks
timers[#timers].callback()
assert(#callbacks == count, "Completed query cancels old retry timers")

events["yabai.observer:display_change"]({})
for i=1,3 do
  callbacks[#callbacks]({spaces={}, windows={}, displays={}, bar_displays={}})
  timers[#timers].callback()
end
local timer_count = #timers
callbacks[#callbacks]("")
assert(#timers == timer_count, "Persistent failures stop after three retries")
assert(items["yabai.space.3"].props.drawing == true, "Unavailable displays preserve the last valid frame")
events["yabai.observer:system_woke"]({})
callbacks[#callbacks](fixture())

local closing = fixture()
closing.windows = {{id=10,pid=100,space=1,app="Terminal"}}
events["yabai.observer:yabai_windows_changed"]({})
callbacks[#callbacks](closing)
events["yabai.observer:yabai_windows_changed"]({}) -- a query started before the close
local stale_query = #callbacks
events["yabai.observer:yabai_windows_changed"]({EVENT="window_destroyed", WINDOW_ID="10"})
assert(items["yabai.space.3.app.1"].props.drawing == false, "Close event removes the app immediately")
callbacks[stale_query](closing)
assert(items["yabai.space.3.app.1"].props.drawing == false, "An old snapshot cannot resurrect the closed window")
callbacks[#callbacks](closing)
assert(items["yabai.space.3.app.1"].props.drawing == false, "Closing animation cannot resurrect the app")
timers[#timers].callback()
local closed = fixture()
closed.windows = {}
callbacks[#callbacks](closed)
assert(items["yabai.space.3.app.1"].props.drawing == false, "Settled close needs no focus change")
assert(items["yabai.space.3"].props.drawing == true, "Empty workspace pill remains available")
events["yabai.observer:yabai_windows_changed"]({EVENT="window_created", WINDOW_ID="10"})
callbacks[#callbacks](closing)
assert(items["yabai.space.3.app.1"].props.drawing == true, "Reused IDs can show new windows")
events["yabai.observer:yabai_windows_changed"]({EVENT="application_terminated", PROCESS_ID="100"})
assert(items["yabai.space.3.app.1"].props.drawing == false, "App termination also removes its icons")
callbacks[#callbacks](closed)
-- A daemon restart first exposes unlabeled desktops, then labels them one by
-- one. Neither intermediate snapshot may create fallback D pills.
events["yabai.observer:display_change"]({})
local restarting = fixture()
restarting.layout = {{index=1,id=100,workspaces={3}},{index=2,id=200,workspaces={2}}}
restarting.spaces[1].label, restarting.spaces[2].label = "", ""
callbacks[#callbacks](restarting)
assert(items["yabai.space.native1"] == nil and items["yabai.space.native2"] == nil,
       "Unlabeled managed desktops must not create duplicate D pills")
timers[#timers].callback()
restarting.spaces[1].label = "ws3"
callbacks[#callbacks](restarting)
assert(items["yabai.space.native2"] == nil, "Partially restored labels are also rejected")
-- Completion is explicit, even if the short query retries already expired.
events["yabai.observer:yabai_windows_changed"]({})
restarting.spaces[2].label = "ws2"
callbacks[#callbacks](restarting)
assert(items["yabai.space.3.app.1"].props.drawing == true, "Label completion restores app icons")
assert(items["yabai.space.2"].props.icon.color == 2, "Restored desktop is no longer a placeholder")
-- Real extra/custom desktops still have fallback pills.
events["yabai.observer:yabai_windows_changed"]({})
restarting.spaces[#restarting.spaces+1] = {index=8,display=1,label="custom",["is-native-fullscreen"]=false}
restarting.spaces[#restarting.spaces+1] = {index=9,display=1,label="",["is-native-fullscreen"]=false}
callbacks[#callbacks](restarting)
assert(items["yabai.space.native8"].props.drawing == true)
assert(items["yabai.space.native9"].props.drawing == true)
-- Focus and minimize/restore can reorder the query without changing membership.
local stable = fixture()
stable.windows = {
  {id=20,space=1,app="Google Chrome"},
  {id=10,space=1,app="T3 Code (Alpha)"},
  {id=30,space=1,app="Google Chrome"},
  {id=40,space=1,app="Spotify"},
}
events["yabai.observer:yabai_windows_changed"]({})
callbacks[#callbacks](stable)
assert(items["yabai.space.3.app.1"].props.background.image == "app.T3 Code (Alpha)")
assert(items["yabai.space.3.app.2"].props.background.image == "app.Google Chrome")
assert(items["yabai.space.3.app.3"].props.background.image == "app.Google Chrome")
assert(items["yabai.space.3.app.4"].props.background.image == "app.Spotify")
for _, minimized in ipairs({true, false}) do
  stable.windows = {stable.windows[4], stable.windows[3], stable.windows[2], stable.windows[1]}
  for _, window in ipairs(stable.windows) do
    window["is-minimized"] = window.id == 30 and minimized
    window["has-focus"] = window.id == (minimized and 20 or 10)
  end
  set_count, animation_count = 0, 0
  events["yabai.observer:yabai_windows_changed"]({})
  callbacks[#callbacks](stable)
  -- Only the minimized Chrome window's M badge toggles; no icon moves.
  assert(set_count == 1 and animation_count == 0,
         "Query reordering, focus, and minimize/restore must not move app icons")
  assert(items["yabai.space.3.app.3"].props.background.image == "app.Google Chrome")
  assert(items["yabai.space.3.app.3"].props.label.drawing == minimized)
end
print("SketchyBar rendering, stable app order, persistent slots, display mapping, clicks, and event coalescing passed")
