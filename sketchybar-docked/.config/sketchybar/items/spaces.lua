local colors = require("colors")
local settings = require("settings")

local spaces = {}
local space_brackets = {}
local space_icon_slots = {} -- native macOS app-icon image items, per workspace
local space_trails = {}     -- trailing pad so the last icon isn't flush to the edge

-- ============================================================================
-- WORKSPACE COUNT CONFIGURATION
-- ============================================================================
-- Change this number to add/remove workspaces (e.g., 6, 9, etc.)
-- Also update aerospace.toml keyboard shortcuts to match:
--   - Add: cmd-N = 'workspace N'
--   - Add: cmd-shift-N = 'move-node-to-workspace N --focus-follows-window'
-- ============================================================================
local WORKSPACE_COUNT = 6

-- ============================================================================
-- MULTI-MONITOR WORKSPACE ASSIGNMENT
-- ============================================================================
-- Mirror aerospace.toml's [workspace-to-monitor-force-assignment]:
--   odd workspaces (1, 3, 5) -> main monitor (display 1)
--   even workspaces (2, 4, 6) -> secondary monitor (display 2)
-- Each space item is pinned to its monitor via `display`, so a monitor's bar
-- only shows the workspaces that live on it (not all 1-6 on every screen).
--
-- Computed dynamically from aerospace itself: ask each monitor which
-- workspaces live on it and pin those pills to that display. aerospace's
-- monitor index lines up with sketchybar's display index (monitor 1 = the
-- left screen = display 1, etc.). With a single display (laptop alone) every
-- workspace collapses onto display 1 so nothing is orphaned.
--
-- NOTE: the pills are plain `item`s, not `space`s. A `space` item carries a
-- native mission-control-space association whose display mask overrides the
-- `display` property, so it always renders on every monitor. Plain items
-- honor `display`, which is what makes per-monitor pinning actually work.
local function get_display_count()
  local handle = io.popen("aerospace list-monitors 2>/dev/null | wc -l")
  if not handle then return 1 end
  local result = handle:read("*a") or ""
  handle:close()
  local count = tonumber((result:gsub("%s+", ""))) or 1
  return math.max(count, 1)
end

local display_count = get_display_count()

local workspace_to_display = {}
for i = 1, WORKSPACE_COUNT do
  workspace_to_display[i] = 1 -- default: single-display / laptop-alone
end
if display_count >= 2 then
  for mon = 1, display_count do
    local handle = io.popen("aerospace list-workspaces --monitor " .. mon .. " 2>/dev/null")
    if handle then
      local result = handle:read("*a") or ""
      handle:close()
      for ws in result:gmatch("%d+") do
        local n = tonumber(ws)
        if n and n >= 1 and n <= WORKSPACE_COUNT then
          workspace_to_display[n] = mon
        end
      end
    end
  end
end

-- App icons are native macOS images (background.image = "app.<name>"). Unlike a
-- text label, an image does NOT auto-size its item, so each icon needs an
-- explicit box width >= the rendered icon (scale * native) or the images
-- overflow and overlap. One constant size for all states keeps spacing stable.
local SLOTS_PER_SPACE = 5
local ICON_SCALE = 0.7
local ICON_CELL = 29 -- box width per icon; with 0 padding this alone sets icon spacing
local PILL_HEIGHT = 30 -- resting pill height
local PILL_HEIGHT_FOCUSED = 36 -- focused pill grows taller so it stands out (bar is 40)
local PILL_RADIUS = 9
local PILL_RADIUS_FOCUSED = 11
local NUMBER_SIZE = 14.0
local NUMBER_SIZE_FOCUSED = 18.0 -- focused workspace number grows with the pill

for i = 1, WORKSPACE_COUNT, 1 do
  -- Space item carries the workspace number; the bracket below is the visible
  -- pill (so the highlight wraps the number AND the icons as one element).
  local space = sbar.add("item", "space." .. i, {
    display = workspace_to_display[i],
    icon = {
      font = { family = settings.font.numbers, size = 14.0 },
      string = i,
      padding_left = 10,
      padding_right = 5,
      color = colors.white,
      highlight_color = colors.mauve,
    },
    label = { drawing = false },
    background = { color = colors.transparent, border_width = 0 },
    padding_left = 2,
    padding_right = 2,
    popup = { background = { border_width = 5, border_color = colors.black } }
  })
  spaces[i] = space

  -- one fixed-width image slot per app (drawn on demand)
  local slots = {}
  local bracket_members = { space.name }
  for s = 1, SLOTS_PER_SPACE do
    local slot = sbar.add("item", "space." .. i .. ".icon." .. s, {
      position = "left",
      display = workspace_to_display[i],
      drawing = false,
      width = ICON_CELL,
      padding_left = 0,  -- explicit: don't inherit the global 5/5 item padding
      padding_right = 0, -- so ICON_CELL is the ONLY thing setting icon spacing
      icon = { drawing = false },
      label = { drawing = false },
      background = {
        drawing = true,
        color = colors.transparent,
        border_width = 0,
        height = 24,
        image = { scale = ICON_SCALE, corner_radius = 5, drawing = true },
      },
    })
    slots[s] = slot
    bracket_members[#bracket_members + 1] = slot.name
  end
  space_icon_slots[i] = slots

  -- trailing pad so the last icon isn't flush against the pill's right edge
  -- (kept small so the right gap matches the spacing between icons)
  local trail = sbar.add("item", "space." .. i .. ".trail", {
    position = "left",
    display = workspace_to_display[i],
    drawing = false,
    width = 4,
    padding_left = 0,
    padding_right = 0,
    icon = { drawing = false },
    label = { drawing = false },
    background = { drawing = false },
  })
  space_trails[i] = trail
  bracket_members[#bracket_members + 1] = trail.name

  -- The bracket IS the pill: fill + border + focus highlight. Matches the
  -- right-side widget pills (default.lua): bg1 fill + soft bg2 2px border.
  local space_bracket = sbar.add("bracket", "space.bracket." .. i, bracket_members, {
    display = workspace_to_display[i],
    background = {
      color = colors.bg1,
      border_color = colors.bg2,
      border_width = 2,
      height = PILL_HEIGHT,
      corner_radius = PILL_RADIUS,
    }
  })
  space_brackets[i] = space_bracket

  -- Padding space between pills
  sbar.add("item", "space.padding." .. i, {
    display = workspace_to_display[i],
    script = "",
    width = settings.group_paddings,
  })

  local space_popup = sbar.add("item", {
    position = "popup." .. space.name,
    padding_left = 5,
    padding_right = 0,
    background = { drawing = true, image = { corner_radius = 9, scale = 0.2 } }
  })

  -- Click anywhere on the pill (number or any icon) acts on the space
  local function on_click(env)
    if env.BUTTON == "other" then
      space_popup:set({ background = { image = "space." .. env.SID } })
      space:set({ popup = { drawing = "toggle" } })
    elseif env.BUTTON == "right" then
      sbar.exec("aerospace workspace " .. i .. " && aerospace close-all-windows-but-current")
    else
      sbar.exec("aerospace workspace " .. i)
    end
  end
  space:subscribe("mouse.clicked", on_click)
  for _, slot in ipairs(slots) do
    slot:subscribe("mouse.clicked", on_click)
  end

  space:subscribe("mouse.exited", function(_)
    space:set({ popup = { drawing = false } })
  end)
end

-- Highlight the focused workspace (number + pill); the focused pill grows
-- taller and the whole transition is animated so it visibly "pops" on switch.
local function set_focus(focused)
  sbar.animate("sin", 14, function()
    for i = 1, WORKSPACE_COUNT do
      local is_focused = (focused == i)
      if spaces[i] then
        spaces[i]:set({
          icon = {
            highlight = is_focused,
            font = { size = is_focused and NUMBER_SIZE_FOCUSED or NUMBER_SIZE },
          },
        })
      end
      if space_brackets[i] then
        space_brackets[i]:set({
          background = {
            color = is_focused and colors.bg2 or colors.bg1,
            border_color = is_focused and colors.mauve or colors.bg2,
            border_width = 2,
            height = is_focused and PILL_HEIGHT_FOCUSED or PILL_HEIGHT,
            corner_radius = is_focused and PILL_RADIUS_FOCUSED or PILL_RADIUS,
          }
        })
      end
    end
  end)
end

local workspace_handler = sbar.add("item", { drawing = false, updates = true })
workspace_handler:subscribe("aerospace_workspace_change", function(env)
  set_focus(tonumber(env.FOCUSED_WORKSPACE))
end)

-- seed the focus highlight on load (the event only fires on change)
sbar.exec("aerospace list-workspaces --focused", function(result)
  set_focus(tonumber((result or ""):gsub("%s+", "")))
end)

-- Replace the glyph label with native app icons, one per app (deduped, capped)
local space_window_observer = sbar.add("item", { drawing = false, updates = true })
local function update_workspace_icons()
  for i = 1, WORKSPACE_COUNT do
    sbar.exec("aerospace list-windows --workspace " .. i .. " --format '%{app-name}'", function(result)
      local slots = space_icon_slots[i]
      local idx = 0
      local seen = {}
      for app_name in result:gmatch("[^\r\n]+") do
        if app_name and app_name ~= "" and not seen[app_name] then
          seen[app_name] = true
          if idx < #slots then
            idx = idx + 1
            slots[idx]:set({ drawing = true, background = { image = "app." .. app_name } })
          end
        end
      end
      for s = idx + 1, #slots do
        slots[s]:set({ drawing = false })
      end
      if space_trails[i] then
        space_trails[i]:set({ drawing = idx > 0 })
      end
      -- empty space: center the number; occupied: left-bias it so icons follow
      if spaces[i] then
        if idx == 0 then
          spaces[i]:set({ icon = { padding_left = 12, padding_right = 12 } })
        else
          spaces[i]:set({ icon = { padding_left = 10, padding_right = 5 } })
        end
      end
    end)
  end
end
space_window_observer:subscribe("aerospace_workspace_change", function(env)
  update_workspace_icons()
end)
update_workspace_icons()
