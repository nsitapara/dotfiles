local colors = require("colors")
local icons = require("icons")
local settings = require("settings")
local app_icons = require("helpers.app_icons")

local spaces = {}
local space_brackets = {}

-- ============================================================================
-- WORKSPACE COUNT CONFIGURATION
-- ============================================================================
-- Change this number to add/remove workspaces (e.g., 6, 9, etc.)
-- Also update aerospace.toml keyboard shortcuts to match:
--   - Add: cmd-N = 'workspace N'
--   - Add: cmd-shift-N = 'move-node-to-workspace N --focus-follows-window'
-- ============================================================================
local WORKSPACE_COUNT = 6

-- Multi-monitor workspace assignment
-- Odd workspaces (1, 3, 5) on main monitor (display 1)
-- Even workspaces (2, 4, 6) on secondary monitor (display 2)
local workspace_to_display = {
  [1] = 1, -- main
  [2] = 2, -- secondary
  [3] = 1, -- main
  [4] = 2, -- secondary
  [5] = 1, -- main
  [6] = 2, -- secondary
}

for i = 1, WORKSPACE_COUNT, 1 do
  local space = sbar.add("space", "space." .. i, {
    space = i,
    display = workspace_to_display[i],
    icon = {
      font = { family = settings.font.numbers },
      string = i,
      padding_left = 12,
      padding_right = 8,
      color = colors.white,
      highlight_color = colors.mauve,
    },
    label = {
      padding_right = 18,
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
      height = 32,
      border_color = colors.black,
    },
    popup = { background = { border_width = 5, border_color = colors.black } }
  })

  spaces[i] = space

  -- Single item bracket for space items (disabled for single border design)
  local space_bracket = sbar.add("bracket", { space.name }, {
    background = {
      color = colors.transparent,
      border_color = colors.transparent,
      height = 34,
      border_width = 0
    }
  })

  space_brackets[i] = space_bracket

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

  space:subscribe("mouse.clicked", function(env)
    if env.BUTTON == "other" then
      space_popup:set({ background = { image = "space." .. i } })
      space:set({ popup = { drawing = "toggle" } })
    else
      -- Use aerospace instead of yabai
      if env.BUTTON == "right" then
        -- Right click: close all windows in workspace
        sbar.exec("aerospace workspace " .. i .. " && aerospace close-all-windows-but-current")
      else
        -- Left click: focus workspace
        sbar.exec("aerospace workspace " .. i)
        -- Manually trigger highlighting update immediately
        sbar.trigger("aerospace_workspace_change", "FOCUSED_WORKSPACE=" .. i)
      end
    end
  end)

  space:subscribe("mouse.exited", function(_)
    space:set({ popup = { drawing = false } })
  end)
end

-- Global event handler for aerospace workspace changes
local workspace_handler = sbar.add("item", {
  drawing = false,
  updates = true,
})

workspace_handler:subscribe("aerospace_workspace_change", function(env)
  local focused_workspace = tonumber(env.FOCUSED_WORKSPACE)

  -- Update all workspaces
  for i = 1, WORKSPACE_COUNT do
    local is_focused = (focused_workspace == i)

    if spaces[i] then
      spaces[i]:set({
        icon = {
          highlight = is_focused,
          padding_left = is_focused and 16 or 12,
          padding_right = is_focused and 12 or 8
        },
        label = {
          highlight = is_focused,
          padding_right = is_focused and 24 or 18
        },
        padding_left = is_focused and 2 or 1,
        padding_right = is_focused and 2 or 1,
        background = {
          border_color = is_focused and colors.mauve or colors.black,
          border_width = is_focused and 2 or 1,
          color = is_focused and colors.bg2 or colors.bg1
        }
      })
    end

    if space_brackets[i] then
      space_brackets[i]:set({
        background = {
          border_color = colors.transparent,
          border_width = 0
        }
      })
    end
  end
end)

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
  for i = 1, WORKSPACE_COUNT do
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
