require("items.apple")
local trial = io.popen("launchctl list local.dotfiles.yabai 2>/dev/null")
local yabai_active = trial and trial:read("*a") ~= ""
if trial then trial:close() end
if yabai_active then
  dofile(os.getenv("HOME") .. "/.config/yabai/sketchybar.lua")
else
  require("items.spaces")
end
require("items.service_mode")(yabai_active)
require("items.center_app")
require("items.calendar")
require("items.widgets")
require("items.display_profile")
require("items.media")
