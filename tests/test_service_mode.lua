local root = assert(arg[1], "Pass the repository path")
package.preload.colors = function() return { mauve=1, bg1=2, white=3 } end
for _, profile in ipairs({"sketchybar", "sketchybar-docked"}) do
  for _, yabai in ipairs({false, true}) do
    local item, events, callbacks, items = nil, {}, {}, {}
    sbar = {
      add = function(kind, name, props)
        if kind == "event" then return end
        local added = { props=props }
        items[name] = added
        if name == "wm.service" then item = added end
        function added:set(values)
          for key, value in pairs(values) do
            if type(value) == "table" and type(self.props[key]) == "table" then
              for k,v in pairs(value) do self.props[key][k] = v end
            else self.props[key] = value end
          end
        end
        function added:subscribe(names, callback)
          if type(names) == "string" then names = {names} end
          for _, event in ipairs(names) do events[event] = callback end
        end
        return added
      end,
      exec = function(_, callback) callbacks[#callbacks+1] = callback end,
    }
    dofile(root .. "/" .. profile .. "/.config/sketchybar/items/service_mode.lua")(yabai)
    assert(item.props.ignore_association == true, "Service mode must show on every monitor")
    assert(item.props.position == "left")
    assert(not item.props.drawing, "Hidden until mode is known")
    callbacks[1]("service\n")
    assert(item.props.drawing, "Restore service mode after a bar reload")
    assert(not items["wm.help.1"], "Help rows are created only on demand")
    events.wm_help_toggle()
    assert(item.props.popup.drawing, "? opens help in service mode")
    assert(items["wm.help.1"].props.label.string == (yabai and "yabai + skhd" or "AeroSpace"))
    assert(items["wm.help.1"].props.position == "popup.wm.service")
    assert(item.props.popup.height == 25)
    local has_close_others, has_insertion, has_merge = false, false, false
    for name, row in pairs(items) do
      if name:match("^wm.help%.") then
        has_close_others = has_close_others or row.props.icon.string == "Backspace"
        has_insertion = has_insertion or row.props.label.string:match("M: insertion$") ~= nil
        has_merge = has_merge or row.props.label.string:match("M: merge$") ~= nil
      end
    end
    assert(has_close_others == not yabai, "Only AeroSpace binds close-other-windows")
    assert(has_insertion == yabai and has_merge == not yabai, "Show manager-specific modes")
    events.wm_help_toggle()
    assert(not item.props.popup.drawing, "? toggles help off")
    events["mouse.clicked"]()
    assert(item.props.popup.drawing, "Clicking SERVICE opens help too")
    local event = yabai and "yabai_mode_changed" or "aerospace_mode_changed"
    events[event]({MODE="default"})
    if not yabai then callbacks[#callbacks]("main\n") end
    assert(not item.props.drawing, "Hide on exit")
    assert(not item.props.popup.drawing, "Mode exit closes the popup")
    events.display_change()
    local stale = callbacks[#callbacks]
    events[event]({MODE="service"})
    if not yabai then callbacks[#callbacks]("service\n") end
    stale("main\n")
    assert(item.props.drawing, "An older query cannot overwrite a newer mode event")
    events[event]({MODE="resize"})
    if not yabai then callbacks[#callbacks]("resize\n") end
    assert(not item.props.drawing, "Other modes must not show SERVICE")
    events.wm_help_toggle()
    callbacks[#callbacks]("service\n")
    assert(item.props.popup.drawing, "A fast help request can refresh a pending service entry")
    events[event]({MODE="default"})
    if not yabai then callbacks[#callbacks]("main\n") end
    assert(not item.props.popup.drawing)
    events.wm_help_toggle()
    callbacks[#callbacks](yabai and "default\n" or "main\n")
    assert(not item.props.popup.drawing, "Ignore help requests outside service mode")
  end
end
print("Service indicator and help popup: all four profiles, toggles, mode-specific content, exit, and async races passed")
