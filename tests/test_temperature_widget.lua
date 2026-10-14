-- Read CPU die average from Stats' bundled CLI without mixing in other sensors.
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
  local events, items, callback = {}, {}, nil
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
        for _, event in ipairs(names) do events[event] = fn end
      end
      items[name] = item
      return item
    end,
    exec = function(_, fn) callback = fn; requests = requests + 1 end,
  }
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/temperature.lua")
  events.routine()
  assert(requests == 1, "A pending sensor read must not overlap another")
  callback("", 1)
  local item = items["widgets.temperature"]
  assert(item.props.label.string == "—", "No reading must remain unavailable")

  for i, case in ipairs({
    { "[INFO]: found 6 keys\n[Te05] 51.4\n[Tp01] 0\n[TCMb] 59.7\n[TCMz] 95\n[Tg05] 100\n[TB0T] 30\n",
      0, "60C", colors.yellow, 1 },
    { "[Te05] 0\n[Tp01] -4\n[TCMb] 68.7\n",
      0, "69C", colors.orange, 2 },
    { "[TCMb] 72\n", 1, "—", colors.orange, 2 },
    { "[Tg05] 70\n[Te05] 60\n[Tp01] 70\n", 0, "—", colors.orange, 2 },
    { "[TCMb] 0\n", 0, "—", colors.orange, 2 },
    { "[TCMb] -4\n", 0, "—", colors.orange, 2 },
    { "[TCMb] nan\n", 0, "—", colors.orange, 2 },
    { "[TCMb] inf\n", 0, "—", colors.orange, 2 },
    { "[TCMb] 999\n", 0, "—", colors.orange, 2 },
    { "invalid", 0, "—", colors.orange, 2 },
    { "", 127, "—", colors.orange, 2 },
    { "[TCMb] 80.1\n", 0, "80C", colors.red, 3 },
  }) do
    events.routine()
    callback(case[1], case[2])
    assert(item.props.label.string == case[3], "Unexpected label in case " .. i)
    assert(item.props.graph.color == case[4], "Temperature color in case " .. i)
    assert(samples == case[5], "Only valid CPU readings belong in the graph")
  end
  local before = requests
  events.system_woke()
  assert(requests == before + 1, "Wake must refresh temperature")
  print(profile .. ": CPU die average, unavailable readings, recovery and graph samples passed")
end
