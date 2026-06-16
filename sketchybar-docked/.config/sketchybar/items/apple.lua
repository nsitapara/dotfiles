local colors = require("colors")
local settings = require("settings")

-- Padding item required because of bracket
sbar.add("item", { width = 5 })

-- [PROTO] far-left indicator: the currently focused aerospace workspace number
local focused_space = sbar.add("item", "focused_space", {
  icon = {
    font = { family = settings.font.numbers, size = 16.0 },
    string = "1",
    padding_right = 11,
    padding_left = 11,
    color = colors.white,
  },
  label = { drawing = false },
  background = {
    color = colors.bg2,
    border_color = colors.black,
    border_width = 1
  },
  padding_left = 1,
  padding_right = 1,
  updates = true,
})

-- Double border using a single item bracket
sbar.add("bracket", { focused_space.name }, {
  background = {
    color = colors.transparent,
    height = 30,
    border_color = colors.grey,
  }
})

-- Padding item required because of bracket
sbar.add("item", { width = 7 })

local function set_focused(n)
  n = (n or ""):gsub("%s+", "")
  if n ~= "" then
    focused_space:set({ icon = { string = n } })
  end
end

focused_space:subscribe("aerospace_workspace_change", function(env)
  set_focused(env.FOCUSED_WORKSPACE)
end)

-- Seed the initial value on load (event only fires on change)
sbar.exec("aerospace list-workspaces --focused", function(result)
  set_focused(result)
end)
