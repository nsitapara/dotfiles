-- The memory widget shows the system_stats provider's reading and graphs only
-- valid ones. The RAM accounting itself is pinned in test_system_stats.c.
local root = assert(arg[1], "Pass repository path")
local colors = { blue = 1, yellow = 2, orange = 3, red = 4, white = 5, grey = 6, bg1 = 7 }
package.preload.colors = function() return colors end
package.preload.icons = function() return { memory = "memory-chip" } end
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
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/memory.lua")
  assert(requests == 0, "Memory must not spawn its own sensor commands")
  local item = items["widgets.memory"]
  assert(item.props.icon.string == "memory-chip", "Use the configured memory icon, not a text label")
  assert(item.props.update_freq == nil, "Memory must not poll on its own timer")

  for i, case in ipairs({
    { "80.0", "80%", 1 },
    { "45.4", "45%", 2 },
    { "-1", "--%", 2 },
    { "", "--%", 2 },
    { "nan", "--%", 2 },
    { "101", "--%", 2 },
    { "99.6", "100%", 3 },
  }) do
    events.system_stats({ mem = case[1] })
    assert(item.props.label.string == case[2], "Unexpected label in case " .. i)
    assert(samples == case[3], "Only valid RAM readings belong in the graph")
  end
  print(profile .. ": memory readings, unavailable values and recovery passed")
end
