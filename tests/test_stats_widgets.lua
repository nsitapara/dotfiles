-- CPU, memory, SSD and temperature widgets: plain icon + number fed by the
-- system_stats provider, coloured by usage, with no graphs, timers or commands.
-- The provider's accounting is pinned in test_system_stats.c.
local root = assert(arg[1], "Pass repository path")
local colors = { blue = 1, yellow = 2, orange = 3, red = 4, white = 5, grey = 6, bg1 = 7 }
local W, Y, O, R = colors.white, colors.yellow, colors.orange, colors.red
package.preload.colors = function() return colors end
package.preload.icons = function()
  return { cpu = "cpu", memory = "memory", disk = "disk", temperature = "thermometer" }
end
package.preload.settings = function()
  return { paddings = 3, group_paddings = 5,
    font = { numbers = "test", style_map = { Regular = "Regular", Semibold = "Semibold" } } }
end

-- { widget file, item name, event field, initial label, cases = { value, label, colour } }
local widgets = {
  { "cpu", "widgets.cpu", "cpu", "--%", {
    { "6", "06%", W }, { "30", "30%", W }, { "45", "45%", Y }, { "70", "70%", O },
    { "95", "95%", R }, { "-1", "--%", W }, { "101", "--%", W }, { "", "--%", W },
  } },
  { "memory", "widgets.memory", "mem", "--%", {
    { "6.2", "06%", W }, { "69.4", "69%", W }, { "75", "75%", Y }, { "85", "85%", O },
    { "99.6", "100%", R }, { "-1", "--%", W }, { "nan", "--%", W }, { "", "--%", W },
  } },
  { "ssd", "widgets.ssd", "disk", "--%", {
    { "7", "07%", W }, { "74", "74%", W }, { "85", "85%", Y }, { "92", "92%", O },
    { "97", "97%", R }, { "-1", "--%", W }, { "101", "--%", W }, { "", "--%", W },
  } },
  { "temperature", "widgets.temperature", "temp", "—", {
    { "59.7", "60C", W }, { "75", "75C", Y }, { "85", "85C", O }, { "92", "92C", R },
    { "-1", "—", W }, { "0", "—", W }, { "nan", "—", W }, { "inf", "—", W },
    { "999", "—", W }, { "", "—", W },
  } },
}

for _, profile in ipairs({ "sketchybar", "sketchybar-docked" }) do
  for _, spec in ipairs(widgets) do
    local file, name, field, initial, cases = spec[1], spec[2], spec[3], spec[4], spec[5]
    local events, items, requests, kinds = {}, {}, 0, {}
    sbar = {
      add = function(kind, item_name, props)
        local item = { name = item_name, props = props }
        kinds[item_name] = kind
        function item:set(values)
          for k, v in pairs(values) do
            self.props[k] = self.props[k] or {}
            for key, value in pairs(v) do self.props[k][key] = value end
          end
        end
        function item:push() error("Stats widgets must not draw graphs") end
        function item:subscribe(names, fn)
          for _, event in ipairs(type(names) == "table" and names or { names }) do events[event] = fn end
        end
        items[item_name] = item
        return item
      end,
      exec = function() requests = requests + 1 end,
    }
    dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/" .. file .. ".lua")
    local item = items[name]
    local where = profile .. " " .. file
    assert(kinds[name] == "item", where .. ": a plain item, not a graph")
    assert(requests == 0 and item.props.update_freq == nil, where .. ": no timers or commands")
    assert(item.props.label.string == initial, where .. ": starts unavailable")

    for i, case in ipairs(cases) do
      events.system_stats({ [field] = case[1] })
      assert(item.props.label.string == case[2], where .. ": label in case " .. i)
      assert(item.props.label.color == case[3], where .. ": colour in case " .. i)
    end
    if file == "ssd" then
      events.system_stats({ cpu = "10", mem = "50.0", temp = "50.0" })
      assert(item.props.label.string == cases[#cases][2], where .. ": ticks without disk leave it alone")
    end
  end
  print(profile .. ": stats widgets' numbers, usage colours and unavailable values passed")
end
