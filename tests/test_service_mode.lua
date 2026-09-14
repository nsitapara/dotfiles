local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function() return { mauve=1, bg1=2 } end
for _, profile in ipairs({"sketchybar", "sketchybar-docked"}) do
  for _, yabai in ipairs({false, true}) do
    local item, events, callbacks = nil, {}, {}
    sbar = {
      add = function(kind, name, props)
        if kind == "event" then return end
        item = { props=props }
        function item:set(values)
          for key, value in pairs(values) do self.props[key] = value end
        end
        function item:subscribe(names, callback)
          if type(names) == "string" then names = {names} end
          for _, event in ipairs(names) do events[event] = callback end
        end
        return item
      end,
      exec = function(_, callback) callbacks[#callbacks+1] = callback end,
    }
    dofile(root .. "/" .. profile .. "/.config/sketchybar/items/service_mode.lua")(yabai)
    assert(item.props.ignore_association == true, "Service mode must show on every monitor")
    assert(item.props.position == "left")
    assert(not item.props.drawing, "Hidden until mode is known")
    callbacks[1]("service\n")
    assert(item.props.drawing, "Restore service mode after a bar reload")
    local event = yabai and "yabai_mode_changed" or "aerospace_mode_changed"
    events[event]({MODE="default"})
    if not yabai then callbacks[#callbacks]("main\n") end
    assert(not item.props.drawing, "Hide on exit")
    events.display_change()
    local stale = callbacks[#callbacks]
    events[event]({MODE="service"})
    if not yabai then callbacks[#callbacks]("service\n") end
    stale("main\n")
    assert(item.props.drawing, "An older query cannot overwrite a newer mode event")
    events[event]({MODE="resize"})
    if not yabai then callbacks[#callbacks]("resize\n") end
    assert(not item.props.drawing, "Other modes must not show SERVICE")
  end
end
print("Service indicator enter/exit, all-display placement, reload state, and stale-query checks passed")
