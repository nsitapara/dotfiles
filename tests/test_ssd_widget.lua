-- The SSD widget updates only on the system_stats provider's disk ticks:
-- disk space as the label, disk0 throughput as a rescaled 36-sample graph.
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
  assert(sets == 0 and #pushes == 0, "CPU-only ticks must leave the SSD widget untouched")

  events.system_stats({ disk = "74", disk_mbps = "5.00" })
  assert(item.props.label.string == "74%" and #pushes == 1, "Disk tick sets label and graph")
  assert(#pushes[1] == 36 and pushes[1][36] == 5 / 10 * 0.3, "Graph keeps 36 samples over a 10 MB/s floor")

  events.system_stats({ disk = "-1", disk_mbps = "-1" })
  assert(item.props.label.string == "--%" and #pushes == 1, "Unavailable disk values are not graphed")

  events.system_stats({ disk = "75", disk_mbps = "20.00" })
  local graph = pushes[2]
  assert(item.props.label.string == "75%", "Recovers after an unavailable reading")
  assert(graph[36] == 0.3 and graph[35] == 5 / 20 * 0.3, "History rescales to the new peak")
  print(profile .. ": SSD disk ticks, CPU-only ticks, unavailable values and rescaling passed")
end
