-- Change the default Omarchy look'n'feel.

-- https://wiki.hypr.land/Configuring/Basics/Variables/#general
hl.config({
  general = {
    gaps_in = 5,
    gaps_out = 5,
  },

  -- https://wiki.hypr.land/Configuring/Basics/Variables/#decoration
  decoration = {
    rounding = 8,
  },
})

-- Keep every window fully opaque. Omarchy's default fades unfocused windows to
-- "0.985 0.96"; this rule runs after that one, so it wins.
o.window(".*", { opacity = "1 1" })

-- Launch this game fullscreen.
o.window("steam_app_1174180", { fullscreen = true })
