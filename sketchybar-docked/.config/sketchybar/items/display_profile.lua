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

-- Same bordered pill and spacing as the other right-side widgets.
sbar.add("bracket", "display.profile.bracket", { menu.name }, { background = { color = colors.bg1 } })
sbar.add("item", "display.profile.padding", { position = "right", width = settings.group_paddings })

local rows, managers, shown = {}, {}, false
local letters = { yabai = "Y", aerospace = "A", rift = "R", none = "Off" }
local active_manager = "none"
local generation = 0
local function refresh()
  generation = generation + 1
  local request = generation
  sbar.exec(wm, function(result)
    if request ~= generation then return end
    -- Output: "<pinned> <applied>". The number follows the pin; a pin the screens
    -- cannot satisfy shows grey; otherwise plain white like the other widgets.
    local pinned, applied, manager = tostring(result):match("^%s*(%S+)%s+(%S+)%s*(%S*)")
    active_manager = manager or "none"
    local shown_profile = number[pinned] and pinned or applied
    local in_effect = not number[pinned] or pinned == applied
    local color = in_effect and colors.white or colors.grey
    menu:set({ icon = { color = color }, label = { string = (number[shown_profile] or "–") .. (active_manager == "yabai" and "" or " " .. (letters[active_manager] or "?")), color = color } })
    for id, row in pairs(managers) do
      row:set({ label = { color = id == active_manager and colors.mauve or colors.white } })
    end
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
sbar.add("item", "display.profile.manager_heading", {
  position = "popup.display.profile", width = 180,
  icon = { drawing = false },
  label = { string = "Window manager", color = colors.grey, align = "left", padding_left = 14, font = { size = 11 } },
})
for _, entry in ipairs({ {"yabai", "yabai - Y"}, {"aerospace", "AeroSpace - A"}, {"rift", "Rift - R"} }) do
  local id, title = entry[1], entry[2]
  local row = sbar.add("item", "display.profile.manager." .. id, {
    position = "popup.display.profile", width = 180,
    icon = { drawing = false },
    label = {
      string = title, align = "left", padding_left = 14, padding_right = 14,
      color = colors.white, font = { family = "SF Pro", style = "Semibold", size = 12 },
    },
    background = { drawing = false },
  })
  managers[id] = row
  row:subscribe("mouse.clicked", function()
    shown = false
    menu:set({ popup = { drawing = false }, label = { string = "…" } })
    -- Alternatives are temporary; yabai stays the saved login default. Keep errors in
    -- the desktop log; a failed switch refreshes the actual manager badge.
    local command = 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"; '
      .. 'mkdir -p "$HOME/.local/state/dotfiles-wm"; '
      .. '"$HOME/dotfiles/wm.sh" use ' .. id .. ' --temporary >>"$HOME/.local/state/dotfiles-wm/menu-switch.log" 2>&1'
    sbar.exec(command, function(_, code)
      if code and code ~= 0 then
        menu:set({ label = { string = "! " .. (letters[active_manager] or "?") } })
      end
      refresh()
    end)
  end)
end
local quit = sbar.add("item", "display.profile.quit", {
  position = "popup.display.profile", width = 180,
  icon = { drawing = false },
  label = { string = "Quit window manager", align = "left", padding_left = 14,
    color = colors.white, font = { size = 12 } },
})
quit:subscribe("mouse.clicked", function()
  shown = false
  menu:set({ popup = { drawing = false }, label = { string = "…" } })
  sbar.exec('export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"; '
    .. 'mkdir -p "$HOME/.local/state/dotfiles-wm"; '
    .. '"$HOME/dotfiles/wm.sh" quit >>"$HOME/.local/state/dotfiles-wm/menu-switch.log" 2>&1', refresh)
end)
menu:subscribe("mouse.clicked", function()
  shown = not shown
  menu:set({ popup = { drawing = shown } })
end)
menu:subscribe({ "display_change", "system_woke" }, refresh)
refresh()
