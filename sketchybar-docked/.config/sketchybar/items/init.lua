require("items.apple")
local trial = io.popen("launchctl list local.dotfiles.yabai 2>/dev/null")
local yabai_active = trial and trial:read("*a") ~= ""
if trial then trial:close() end
local rift_job = io.popen("launchctl list local.dotfiles.rift 2>/dev/null")
local rift_active = rift_job and rift_job:read("*a") ~= ""
if rift_job then rift_job:close() end
local aerospace_job = io.popen("pgrep -x AeroSpace 2>/dev/null")
local aerospace_active = aerospace_job and aerospace_job:read("*a") ~= ""
if aerospace_job then aerospace_job:close() end
local backend = rift_active and "rift" or yabai_active and "yabai" or aerospace_active and "aerospace" or "none"
if rift_active then
  dofile(os.getenv("HOME") .. "/.config/rift/sketchybar.lua")
elseif yabai_active then
  dofile(os.getenv("HOME") .. "/.config/yabai/sketchybar.lua")
elseif aerospace_active then
  require("items.spaces")
end
if backend ~= "none" then require("items.service_mode")(backend) end
require("items.center_app")
require("items.calendar")
require("items.widgets")
require("items.media")
sbar.add("item", "wm.backend", { drawing = false,
  label = { string = backend } })
