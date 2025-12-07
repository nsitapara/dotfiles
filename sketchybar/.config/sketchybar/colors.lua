-- Load colors from current Omarchy theme
local home = os.getenv("HOME")
local theme_path = home .. "/.config/omarchy/current/sketchybar-colors.lua"
return dofile(theme_path)
