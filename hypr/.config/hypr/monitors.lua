-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

hl.env("GDK_SCALE", "1")

-- Explicit positions (not "auto") so monitor power-cycling can't re-swap sides.
-- DP-1 (LG) on the left, DP-2 (ASUS, scale 1.25 -> 2048 logical wide) on the right.
hl.monitor({ output = "DP-1", mode = "2560x1440@74.97", position = "0x0", scale = 1 })
hl.monitor({ output = "DP-2", mode = "2560x1440@74.92", position = "2560x0", scale = 1.25 })

-- Fallback for any other display that gets plugged in.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

-- Workspace assignments: LG monitor gets odd (1,3,5), ASUS gets even (2,4,6).
hl.workspace_rule({ workspace = "1", monitor = "DP-1" })
hl.workspace_rule({ workspace = "2", monitor = "DP-2" })
hl.workspace_rule({ workspace = "3", monitor = "DP-1" })
hl.workspace_rule({ workspace = "4", monitor = "DP-2" })
hl.workspace_rule({ workspace = "5", monitor = "DP-1" })
hl.workspace_rule({ workspace = "6", monitor = "DP-2" })
