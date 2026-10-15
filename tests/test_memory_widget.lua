-- RAM accounting must exclude cache and use the physical compressor size.
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
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/memory.lua")
  events.routine()
  assert(requests == 1, "A pending sensor read must not overlap another")
  callback("", 1)
  local item = items["widgets.memory"]
  assert(item.props.icon.string == "memory-chip", "Use the configured memory icon, not a text label")
  assert(item.props.label.string == "--%", "No reading must remain unavailable")

  local function fixture(page_size)
    return string.format([[%d
Mach Virtual Memory Statistics: (page size of %d bytes)
Anonymous pages: 600.
Pages purgeable: 100.
Pages wired down: 200.
Pages occupied by compressor: 100.
Pages stored in compressor: 400.
File-backed pages: 150.
]], 1000 * page_size, page_size)
  end
  for i, case in ipairs({
    { fixture(16384), 0, "80%", 1 },
    { fixture(4096), 0, "80%", 2 },
    { fixture(16384), 1, "--%", 2 },
    { fixture(16384):gsub("Anonymous pages: 600.\n", ""), 0, "--%", 2 },
    { fixture(16384):gsub("^%d+", "0"), 0, "--%", 2 },
    { "", 0, "--%", 2 },
    { fixture(16384), 0, "80%", 3 },
  }) do
    events.routine()
    callback(case[1], case[2])
    assert(item.props.label.string == case[3], "Unexpected label in case " .. i)
    assert(samples == case[4], "Only valid RAM readings belong in the graph")
  end
  local before = requests
  events.system_woke()
  assert(requests == before + 1, "Wake must refresh memory")
  print(profile .. ": RAM accounting, page sizes, unavailable readings and recovery passed")
end
