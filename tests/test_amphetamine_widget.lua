-- Exercise asynchronous hover/click lifecycles without controlling Amphetamine.
local root = assert(arg[1], "Pass repository path")
package.preload.colors = function()
  return {grey=1, green=2, red=3, white=4, bg1=5, bg2=6, popup={bg=7}}
end
local real_open = io.open
for _, version in ipairs({27, 26}) do
  for _, profile in ipairs({"sketchybar", "sketchybar-docked"}) do
    local items, events, commands = {}, {}, {}
    local function merge(t, v)
      for k, x in pairs(v) do
        if type(x) == "table" then t[k] = t[k] or {}; merge(t[k], x)
        else t[k] = x end
      end
    end
    io.open = function(path, mode)
      if path == "/System/Library/CoreServices/SystemVersion.plist" then
        return {read=function() return "<key>ProductVersion</key><string>" .. version .. ".0</string>" end, close=function() end}
      end
      return real_open(path, mode)
    end
    sbar = {
      add=function(kind, name, props)
        local item={name=name, kind=kind, props=props}
        function item:set(values) merge(self.props, values) end
        function item:subscribe(event, fn)
          for _, e in ipairs(type(event)=="table" and event or {event}) do
            events[name .. ":" .. e]=fn
          end
        end
        items[name]=item; return item
      end,
      exec=function(command, callback) commands[#commands+1]={text=command, callback=callback} end,
    }
    dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/amphetamine.lua")
    io.open=real_open
    local name="Amphetamine,Amphetamine"
    local item=items[name]
    local function event(e, env) events[name .. ":" .. e](env or {}) end
    local function count(fragment)
      local n=0
      for _, c in ipairs(commands) do if c.text:find(fragment, 1, true) then n=n+1 end end
      return n
    end
    event("routine")
    local pending=commands[#commands]
    event("routine")
    assert(count("pmset")==1, "Slow power queries must not overlap")
    pending.callback("", 0)
    if version==27 then
      assert(item.kind=="item" and item.props.update_freq==5)
      assert(count("hover-")==0, "Regular items must not spawn hover polling")
      event("mouse.entered")
      assert(item.props.popup.drawing and item.props.update_freq==1)
      local status=commands[#commands]
      event("mouse.exited")
      status.callback({seconds=100}, 0)
      assert(not item.props.popup.drawing and item.props.update_freq==5,
        "A late status response must not reopen the tooltip")
      event("mouse.entered")
      event("mouse.clicked", {BUTTON="right"})
      assert(not item.props.popup.drawing)
      event("mouse.entered")
      assert(not item.props.popup.drawing, "Native menu click suppresses immediate reentry")
      event("mouse.exited")
      event("mouse.entered")
      assert(item.props.popup.drawing, "A later hover must work after leaving the menu")
      assert(count("hover-")==0)
    else
      assert(item.kind=="alias" and item.props.update_freq==1)
      assert(count("hover-check")==1, "Legacy aliases retain their guarded pointer check")
    end
  end
end
print("Amphetamine widget lifecycle checks passed for both profiles and OS paths")
