-- The SSD widget shows disk space used, as the label and the graph, and
-- updates only when the system_stats provider sends a disk reading.
local root = assert(arg[1], "Pass repository path")
package.preload.colors = function() return { blue = 1, bg1 = 7 } end
package.preload.icons = function() return { disk = "disk" } end
package.preload.settings = function()
  return { paddings = 3, group_paddings = 5,
    font = { numbers = "test", style_map = { Regular = "Regular", Semibold = "Semibold" } } }
end

for _, profile in ipairs({ "sketchybar", "sketchybar-docked" }) do
  local pushes, sets, requests = {}, 0, 0
  local events, items = {}, {}
  sbar = {
    add = function(_, name, props, graph_props)
      local item = { name = name, props = graph_props or props }
      function item:set(values)
        sets = sets + 1
        if values.label then self.props.label.string = values.label end
      end
      function item:push(values) pushes[#pushes + 1] = values end
      function item:subscribe(names, fn)
        for _, event in ipairs(type(names) == "table" and names or { names }) do events[event] = fn end
      end
      items[name] = item
      return item
    end,
    exec = function() requests = requests + 1 end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/ssd.lua")
  local item = items["widgets.ssd"]
  assert(requests == 0 and item.props.update_freq == nil, "SSD must not poll or spawn commands")

  events.system_stats({ cpu = "10", mem = "50.0", temp = "50.0" })
  assert(sets == 0 and #pushes == 0, "Ticks without a disk reading leave the SSD widget untouched")

  for i, case in ipairs({
    { "74", "74%", 1, 0.74 * 0.3 },
    { "-1", "--%", 1 },
    { "", "--%", 1 },
    { "101", "--%", 1 },
    { "75", "75%", 2, 0.75 * 0.3 },
  }) do
    events.system_stats({ disk = case[1] })
    assert(item.props.label.string == case[2], "Unexpected label in case " .. i)
    assert(#pushes == case[3], "Only valid disk readings belong in the graph, case " .. i)
    if case[4] then
      assert(math.abs(pushes[#pushes][1] - case[4]) < 1e-12, "Graph plots used space, case " .. i)
    end
  end
  print(profile .. ": SSD space label and graph, ticks without disk, unavailable values passed")
end
