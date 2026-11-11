-- The temperature widget shows the system_stats provider's CPU die average
-- (SMC key TCMb) with colour bands and graphs only valid readings.
local root = assert(arg[1], "Pass repository path")
local colors = { blue = 1, yellow = 2, orange = 3, red = 4, white = 5, grey = 6, bg1 = 7 }
package.preload.colors = function() return colors end
package.preload.icons = function() return { temperature = "thermometer" } end
package.preload.settings = function()
  return { paddings = 3, group_paddings = 5,
    font = { numbers = "test", style_map = { Regular = "Regular", Semibold = "Semibold" } } }
end

for _, profile in ipairs({ "sketchybar", "sketchybar-docked" }) do
  local samples, requests = 0, 0
  local events, items = {}, {}
  sbar = {
    add = function(_, name, props, graph_props)
      local item = { name = name, props = graph_props or props }
      function item:set(values)
        for k, v in pairs(values) do
          if type(v) == "table" then
            self.props[k] = self.props[k] or {}
            for key, value in pairs(v) do self.props[k][key] = value end
          elseif k == "label" then self.props.label.string = v
          else self.props[k] = v end
        end
      end
      function item:push() samples = samples + 1 end
      function item:subscribe(names, fn)
        for _, event in ipairs(type(names) == "table" and names or { names }) do events[event] = fn end
      end
      items[name] = item
      return item
    end,
    exec = function() requests = requests + 1 end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/temperature.lua")
  assert(requests == 0, "Temperature must not spawn its own sensor commands")
  local item = items["widgets.temperature"]
  assert(item.props.label.string == "—", "No reading must remain unavailable")
  assert(item.props.update_freq == nil, "Temperature must not poll on its own timer")

  for i, case in ipairs({
    { "59.7", "60C", colors.yellow, 1 },
    { "68.7", "69C", colors.orange, 2 },
    { "-1", "—", colors.orange, 2 },
    { "0", "—", colors.orange, 2 },
    { "nan", "—", colors.orange, 2 },
    { "inf", "—", colors.orange, 2 },
    { "999", "—", colors.orange, 2 },
    { "", "—", colors.orange, 2 },
    { "80.1", "80C", colors.red, 3 },
  }) do
    events.system_stats({ temp = case[1] })
    assert(item.props.label.string == case[2], "Unexpected label in case " .. i)
    assert(item.props.graph.color == case[3], "Temperature color in case " .. i)
    assert(samples == case[4], "Only valid CPU readings belong in the graph")
  end
  print(profile .. ": temperature readings, colour bands, unavailable values and recovery passed")
end
