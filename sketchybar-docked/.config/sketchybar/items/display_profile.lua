-- Display profile menu: a monitor icon plus the number of external screens the
-- pinned profile uses (2, 1, or 0). Profiles are pinned by hand; nothing polls.
local colors = require("colors")
local settings = require("settings")
local order = { "docked", "single", "laptop" }
local number = { docked = "2", single = "1", laptop = "0" }
local titles = { docked = "2 monitors", single = "1 monitor", laptop = "Laptop only" }
local wm = 'export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"; "$HOME/dotfiles/wm.sh" profile'

local menu = sbar.add("item", "display.profile", {
  position = "right", updates = true,
  icon = {
    string = "\u{100657}", color = colors.white,
    font = { style = settings.font.style_map["Regular"], size = 16.0 },
  },
  label = {
    string = "–", color = colors.white,
    font = { family = settings.font.numbers, style = settings.font.style_map["Semibold"], size = 13.0 },
  },
  popup = {
    drawing = false, align = "right", height = 25,
    background = { color = colors.bg1, border_color = colors.mauve, border_width = 1, corner_radius = 9 },
  },
})

local rows, shown = {}, false
local function refresh()
  sbar.exec(wm, function(result)
    -- Output: "<pinned> <applied>". The number follows the pin; a pin the screens
    -- cannot satisfy shows grey; otherwise plain white like the other widgets.
    local pinned, applied = tostring(result):match("^%s*(%S+)%s+(%S+)")
    local shown_profile = number[pinned] and pinned or applied
    local in_effect = not number[pinned] or pinned == applied
    local color = in_effect and colors.white or colors.grey
    menu:set({ icon = { color = color }, label = { string = number[shown_profile] or "–", color = color } })
    for id, row in pairs(rows) do
      row:set({ label = { color = id == pinned and colors.mauve or colors.white } })
    end
  end)
end
for _, id in ipairs(order) do
  local row = sbar.add("item", "display.profile." .. id, {
    position = "popup.display.profile", width = 160,
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
