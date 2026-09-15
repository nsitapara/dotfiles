-- Display profile menu. Profiles are pinned by hand; nothing polls displays.
local colors = require("colors")
local order = { "auto", "docked", "single", "laptop" }
local short = { auto = "AUTO", docked = "2 MON", single = "1 MON", laptop = "LAPTOP" }
local titles = { auto = "Auto (detect once)", docked = "2 monitors", single = "1 monitor", laptop = "Laptop only" }
local wm = 'export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"; "$HOME/dotfiles/wm.sh" profile'

local menu = sbar.add("item", "display.profile", {
  position = "right", updates = true,
  icon = { drawing = false },
  label = {
    string = "…", color = colors.mauve,
    font = { size = 11.0, style = "Bold" }, padding_left = 9, padding_right = 9,
  },
  background = {
    drawing = true, color = colors.bg1, border_color = colors.mauve,
    border_width = 1, height = 26, corner_radius = 7,
  },
  padding_left = 4, padding_right = 4,
  popup = {
    drawing = false, align = "right", height = 25,
    background = { color = colors.bg1, border_color = colors.mauve, border_width = 1, corner_radius = 9 },
  },
})

local rows, shown = {}, false
local function refresh()
  sbar.exec(wm, function(result)
    -- Output: "<pinned> <applied>". A pin the screens cannot satisfy is greyed.
    local pinned, applied = tostring(result):match("^%s*(%S+)%s+(%S+)")
    pinned = pinned or "auto"
    local in_effect = pinned == "auto" or pinned == applied
    menu:set({ label = { string = short[pinned] or pinned:upper(), color = in_effect and colors.mauve or colors.grey } })
    for id, row in pairs(rows) do
      row:set({ label = { color = id == pinned and colors.mauve or colors.white } })
    end
  end)
end
for _, id in ipairs(order) do
  local row = sbar.add("item", "display.profile." .. id, {
    position = "popup.display.profile", width = 180,
    icon = { drawing = false },
    label = {
      string = titles[id], align = "left", padding_left = 14, padding_right = 14,
      color = colors.white, font = { family = "SF Pro", size = 12.0 },
    },
    background = { drawing = false },
  })
  row:subscribe("mouse.clicked", function()
    shown = false
    menu:set({ popup = { drawing = false } })
    sbar.exec(wm .. " " .. id .. " >/dev/null 2>&1; true", refresh)
  end)
  rows[id] = row
end
menu:subscribe("mouse.clicked", function()
  shown = not shown
  menu:set({ popup = { drawing = shown } })
end)
menu:subscribe({ "display_change", "system_woke" }, refresh)
refresh()
