local colors = require("colors")
-- Avoid io.popen/pclose: SbarLua children inherit unusual SIGCHLD handling.
local version_file = io.open("/System/Library/CoreServices/SystemVersion.plist", "r")
local version_xml = version_file and version_file:read("*a") or ""
if version_file then version_file:close() end
local version = version_xml:match("<key>ProductVersion</key>%s*<string>(%d+)") or "0"
local native_items = (tonumber(version:match("^%d+")) or 0) >= 27
local items = {}
local status_pending = false
local function refresh()
  if status_pending then return end
  status_pending = true
  sbar.exec('/usr/bin/python3 "$HOME/dotfiles/scripts/menu-status.py" status', function(result, code)
    status_pending = false
    for provider, item in pairs(items) do
      local text = code == 0 and type(result) == "table" and result[provider] or "?"
      item:set({ label = { string = text or "--" } })
    end
  end)
end

-- CodexBar must have Merge Icons disabled. macOS 27 no longer exposes these
-- status-item windows to SketchyBar's aliases, so read the app's AX titles.
-- Older systems use the original aliases and need Screen Recording.
for _, provider in ipairs({ "codex", "claude" }) do
  local alias_name = "CodexBar,codexbar-" .. provider
  local item = sbar.add(native_items and "item" or "alias", alias_name, {
    position = "right",
    width = "dynamic",
    alias = not native_items and { scale = 1.0, color = colors.white, update_freq = 5 } or nil,
    update_freq = native_items and provider == "codex" and 5 or 0,
    icon = { drawing = native_items, string = provider == "codex" and ":openai:" or ":claude:",
      font = "sketchybar-app-font:Regular:18.0", padding_left = 8, padding_right = 4 },
    label = { drawing = native_items, string = "--", padding_right = 8 },
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
    click_script = native_items
      and '/usr/bin/python3 "$HOME/dotfiles/scripts/menu-status.py" open ' .. provider
      or '"$CONFIG_DIR/helpers/menus/bin/menus" -s "' .. alias_name .. '"',
  })
  items[provider] = item
  if native_items and provider == "codex" then
    item:subscribe({ "routine", "forced", "system_woke" }, refresh)
  end
end
if native_items then refresh() end
