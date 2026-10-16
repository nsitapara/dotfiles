-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

-- Omarchy's display adjuster persists these values when changing scale.
local omarchy_gdk_scale = 1
local omarchy_monitor_scale = 1.25

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))

-- Place screens automatically so scale changes cannot leave a fixed pixel gap.
-- Keep LG on the left, ASUS on the right, and retain their 75Hz modes.
hl.monitor({ output = "DP-1", mode = "2560x1440@74.97", position = "auto-left", scale = omarchy_monitor_scale })
hl.monitor({ output = "DP-2", mode = "2560x1440@74.92", position = "auto-right", scale = omarchy_monitor_scale })

-- Fallback for any other display that gets plugged in.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Workspace assignments: LG monitor gets odd (1,3,5), ASUS gets even (2,4,6).
hl.workspace_rule({ workspace = "1", monitor = "DP-1", persistent = true })
hl.workspace_rule({ workspace = "2", monitor = "DP-2", persistent = true })
hl.workspace_rule({ workspace = "3", monitor = "DP-1", persistent = true })
hl.workspace_rule({ workspace = "4", monitor = "DP-2", persistent = true })
hl.workspace_rule({ workspace = "5", monitor = "DP-1", persistent = true })
hl.workspace_rule({ workspace = "6", monitor = "DP-2", persistent = true })
