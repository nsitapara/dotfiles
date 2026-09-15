local colors = require("colors")

-- CodexBar must have Merge Icons disabled. Target each provider's stable window
-- name rather than its menu-bar position or the inactive merged status item.
-- SketchyBar needs Screen Recording; the menus helper needs Accessibility.
for _, provider in ipairs({ "codex", "claude" }) do
  local alias_name = "CodexBar,codexbar-" .. provider
  sbar.add("alias", alias_name, {
    position = "right",
    width = "dynamic",
    alias = { scale = 1.0, color = colors.white, update_freq = 5 },
    icon = { drawing = false },
    label = { drawing = false },
    -- One five-point gap per card; padding both sides doubles the spacing.
    padding_left = 5,
    padding_right = 0,
    -- Draw the pill on the alias itself so the image and background share
    -- the same bounds. Separate brackets misalign with fixed-width aliases.
    background = {
      drawing = true,
      color = colors.bg1,
      border_color = colors.bg2,
      border_width = 2,
      height = 28,
      corner_radius = 9,
    },
    click_script = '"$CONFIG_DIR/helpers/menus/bin/menus" -s "' .. alias_name .. '"',
  })
end
