local colors = require("colors")
local icons = require("icons")
local settings = require("settings")
local app_icons = require("helpers.app_icons")

local spaces = {}

-- Workspace to monitor mapping based on aerospace config
-- main monitor (display 1): workspaces 1, 3, 5
-- secondary monitor (display 2): workspaces 2, 4, 6
local workspace_to_display = {
  [1] = 1, -- main
  [2] = 2, -- secondary
  [3] = 1, -- main
  [4] = 2, -- secondary
  [5] = 1, -- main
  [6] = 2, -- secondary
}

for i = 1, 6, 1 do
  local space = sbar.add("space", "space." .. i, {
    space = i,
    display = workspace_to_display[i],
    icon = {
      font = { family = settings.font.numbers },
      string = i,
      padding_left = 15,
      padding_right = 8,
      color = colors.white,
      highlight_color = colors.red,
    },
    label = {
      padding_right = 20,
      color = colors.grey,
      highlight_color = colors.white,
      font = "sketchybar-app-font:Regular:16.0",
      y_offset = -1,
    },
    padding_right = 1,
    padding_left = 1,
    background = {
      color = colors.bg1,
      border_width = 1,
      height = 26,
      border_color = colors.black,
    },
    popup = { background = { border_width = 5, border_color = colors.black } }
  })

  spaces[i] = space

  -- Single item bracket for space items to achieve double border on highlight
  local space_bracket = sbar.add("bracket", { space.name }, {
    background = {
      color = colors.transparent,
      border_color = colors.bg2,
      height = 28,
      border_width = 2
    }
  })

  -- Padding space
  sbar.add("space", "space.padding." .. i, {
    space = i,
    display = workspace_to_display[i],
    script = "",
    width = settings.group_paddings,
  })

  local space_popup = sbar.add("item", {
    position = "popup." .. space.name,
    padding_left= 5,
    padding_right= 0,
    background = {
      drawing = true,
      image = {
        corner_radius = 9,
        scale = 0.2
      }
    }
  })

  -- Subscribe to aerospace workspace change event
  space:subscribe("aerospace_workspace_change", function(env)
    local focused_workspace = env.FOCUSED_WORKSPACE
    local is_focused = (focused_workspace == tostring(i))

    space:set({
      icon = { highlight = is_focused },
      label = { highlight = is_focused },
      background = { border_color = is_focused and colors.black or colors.bg2 }
    })
    space_bracket:set({
      background = { border_color = is_focused and colors.grey or colors.bg2 }
    })
  end)

  space:subscribe("mouse.clicked", function(env)
    if env.BUTTON == "other" then
      space_popup:set({ background = { image = "space." .. env.SID } })
      space:set({ popup = { drawing = "toggle" } })
    else
      -- Use aerospace instead of yabai
      if env.BUTTON == "right" then
        -- Right click: close all windows in workspace
        sbar.exec("aerospace workspace " .. env.SID .. " && aerospace close-all-windows-but-current")
      else
        -- Left click: focus workspace
        sbar.exec("aerospace workspace " .. env.SID)
      end
    end
  end)

  space:subscribe("mouse.exited", function(_)
    space:set({ popup = { drawing = false } })
  end)
end

local space_window_observer = sbar.add("item", {
  drawing = false,
  updates = true,
})

local spaces_indicator = sbar.add("item", {
  padding_left = -3,
  padding_right = 0,
  icon = {
    padding_left = 8,
    padding_right = 9,
    color = colors.grey,
    string = icons.switch.on,
  },
  label = {
    width = 0,
    padding_left = 0,
    padding_right = 8,
    string = "Spaces",
    color = colors.bg1,
  },
  background = {
    color = colors.with_alpha(colors.grey, 0.0),
    border_color = colors.with_alpha(colors.bg1, 0.0),
  }
})

-- Function to update workspace icons using aerospace
local function update_workspace_icons()
  for i = 1, 6 do
    sbar.exec("aerospace list-windows --workspace " .. i .. " --format '%{app-name}'", function(result)
      local icon_line = ""
      local has_windows = false

      -- Parse the result line by line
      for app_name in result:gmatch("[^\r\n]+") do
        if app_name and app_name ~= "" then
          has_windows = true
          local lookup = app_icons[app_name]
          local icon = lookup or app_icons["Default"] or "●"
          icon_line = icon_line .. icon
        end
      end

      if not has_windows then
        icon_line = " —"
      end

      if spaces[i] then
        sbar.animate("tanh", 10, function()
          spaces[i]:set({ label = icon_line })
        end)
      end
    end)
  end
end

-- Update icons when workspace changes
space_window_observer:subscribe("aerospace_workspace_change", function(env)
  update_workspace_icons()
end)

-- Initial icon update
update_workspace_icons()

spaces_indicator:subscribe("swap_menus_and_spaces", function(env)
  local currently_on = spaces_indicator:query().icon.value == icons.switch.on
  spaces_indicator:set({
    icon = currently_on and icons.switch.off or icons.switch.on
  })
end)

spaces_indicator:subscribe("mouse.entered", function(env)
  sbar.animate("tanh", 30, function()
    spaces_indicator:set({
      background = {
        color = { alpha = 1.0 },
        border_color = { alpha = 1.0 },
      },
      icon = { color = colors.bg1 },
      label = { width = "dynamic" }
    })
  end)
end)

spaces_indicator:subscribe("mouse.exited", function(env)
  sbar.animate("tanh", 30, function()
    spaces_indicator:set({
      background = {
        color = { alpha = 0.0 },
        border_color = { alpha = 0.0 },
      },
      icon = { color = colors.grey },
      label = { width = 0, }
    })
  end)
end)

spaces_indicator:subscribe("mouse.clicked", function(env)
  sbar.trigger("swap_menus_and_spaces")
end)
