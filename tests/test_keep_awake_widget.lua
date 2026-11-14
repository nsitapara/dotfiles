-- The coffee-cup widget: draws what the keep_awake provider reports and sends
-- the menu's choices to it. The provider's rules are pinned in test_keep_awake.swift.
local root = assert(arg[1], "Pass repository path")
local colors = { grey = 1, green = 2, white = 3, bg1 = 4, bg2 = 5, popup = { bg = 6 } }
package.preload.colors = function() return colors end
local real_time = os.time

for _, profile in ipairs({ "sketchybar", "sketchybar-docked" }) do
  local items, events, commands = {}, {}, {}
  local function merge(target, values)
    for key, value in pairs(values) do
      if type(value) == "table" then
        target[key] = target[key] or {}
        merge(target[key], value)
      else
        target[key] = value
      end
    end
  end
  sbar = {
    add = function(kind, name, props)
      local item = { name = name, kind = kind, props = props or {} }
      function item:set(values) merge(self.props, values) end
      function item:subscribe(event, fn)
        for _, e in ipairs(type(event) == "table" and event or { event }) do
          events[name .. ":" .. e] = fn
        end
      end
      items[name] = item
      return item
    end,
    exec = function(command, callback) commands[#commands + 1] = { text = command, callback = callback } end,
  }
  os.time = function() return 1000 end
  dofile(root .. "/" .. profile .. "/.config/sketchybar/items/widgets/keep_awake.lua")

  local cup, status = items["widgets.keep_awake"], items["keep_awake.status"]
  local function fire(name, event, env) events[name .. ":" .. event](env or {}) end
  local function ran(suffix)
    local text = commands[#commands].text
    return text:sub(-#suffix) == suffix
  end
  local function shown(id) return items["keep_awake." .. id].props.drawing ~= false end

  assert(commands[1].text:find("keep_awake daemon keep_awake", 1, true), "The provider starts with the bar")
  assert(cup.kind == "item" and cup.props.update_freq == 0, "No timer while the menu is closed")

  -- The provider's first report can be missed, so the widget asks once.
  assert(ran("keep_awake status"))
  commands[#commands].callback({ awake = 1, mode = "auto", power = "AC", ends = 0 }, 0)
  assert(cup.props.icon.color == colors.green and status.props.label.string == "Awake · plugged in")
  assert(shown("off") and not shown("auto"))

  fire(cup.name, "keep_awake", { awake = "0", mode = "auto", power = "BATTERY", ends = "0" })
  assert(cup.props.icon.color == colors.grey and status.props.label.string == "Off · on battery")
  assert(not shown("off") and not shown("auto"))

  fire(cup.name, "keep_awake", { awake = "0", mode = "off", power = "AC", ends = "0" })
  assert(status.props.label.string == "Off · back on at the next plug-in")
  assert(not shown("off") and shown("auto"))

  fire(cup.name, "keep_awake", { awake = "1", mode = "on", power = "BATTERY", ends = "0" })
  assert(status.props.label.string == "Awake · no time limit")
  assert(shown("off") and not shown("auto"))

  -- A click opens the menu; the countdown ticks only while it is open.
  fire(cup.name, "keep_awake", { awake = "1", mode = "on", power = "AC", ends = "6500" })
  assert(shown("off") and shown("auto"))
  fire(cup.name, "mouse.clicked")
  assert(cup.props.popup.drawing and cup.props.update_freq == 1)
  assert(status.props.label.string == "Awake · 1h 31m 40s left")
  os.time = function() return 1001 end
  fire(cup.name, "routine")
  assert(status.props.label.string == "Awake · 1h 31m 39s left")
  fire(cup.name, "mouse.clicked")
  assert(not cup.props.popup.drawing and cup.props.update_freq == 0)
  fire(cup.name, "mouse.clicked")
  fire(cup.name, "mouse.exited.global")
  assert(not cup.props.popup.drawing and cup.props.update_freq == 0)

  -- Each menu row sends its choice to the provider and closes the menu.
  for id, command in pairs({
    ["30m"] = "set on 1800", ["1h"] = "set on 3600", ["2h"] = "set on 7200",
    unlimited = "set on", custom = "custom", off = "set off", auto = "set auto",
  }) do
    fire(cup.name, "mouse.clicked")
    fire("keep_awake." .. id, "mouse.clicked")
    assert(ran("keep_awake " .. command), id)
    assert(not cup.props.popup.drawing, id)
  end

  for _, event in ipairs({ "power_source_change", "system_woke" }) do
    fire(cup.name, event)
    assert(ran("keep_awake sync"), event)
  end
  os.time = real_time
end
print("keep_awake widget checks passed for both profiles")
