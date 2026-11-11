local colors = require("colors")
-- Avoid io.popen/pclose: SbarLua children inherit unusual SIGCHLD handling.
local version_file = io.open("/System/Library/CoreServices/SystemVersion.plist", "r")
local version_xml = version_file and version_file:read("*a") or ""
if version_file then version_file:close() end
local version = version_xml:match("<key>ProductVersion</key>%s*<string>(%d+)") or "0"
local native_items = (tonumber(version:match("^%d+")) or 0) >= 27
local items = {}
local usage_pages = {
  claude = "https://claude.ai/settings/usage",
  codex = "https://chatgpt.com/codex/settings/usage",
}

-- macOS 27 no longer exposes CodexBar's status-item windows to SketchyBar's
-- aliases, so the native ai_usage provider asks Claude's and Codex's usage
-- endpoints directly every 5 minutes (Anthropic rate-limits faster polling) and
-- fires "ai_usage"; no CodexBar app, CLI or Python is involved. Older systems
-- use the original CodexBar aliases (Merge Icons off) and need Screen Recording.
if native_items then
  sbar.add("event", "ai_usage")
  sbar.exec("killall ai_usage >/dev/null 2>&1; "
    .. "exec $CONFIG_DIR/helpers/event_providers/ai_usage/bin/ai_usage ai_usage 300")
end

for _, provider in ipairs({ "codex", "claude" }) do
  local alias_name = "CodexBar,codexbar-" .. provider
  local item = sbar.add(native_items and "item" or "alias", alias_name, {
    position = "right",
    width = "dynamic",
    alias = not native_items and { scale = 1.0, color = colors.white, update_freq = 5 } or nil,
    icon = { drawing = native_items, string = provider == "codex" and ":openai:" or ":claude:",
      color = provider == "claude" and colors.orange or colors.white,
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
      and "open " .. usage_pages[provider]
      or '"$CONFIG_DIR/helpers/menus/bin/menus" -s "' .. alias_name .. '"',
  })
  items[provider] = item
end

if native_items then
  -- A provider missing from the event failed this round; keep its last reading.
  items.codex:subscribe("ai_usage", function(env)
    for provider, item in pairs(items) do
      if env[provider] then item:set({ label = { string = env[provider] } }) end
    end
  end)
end
