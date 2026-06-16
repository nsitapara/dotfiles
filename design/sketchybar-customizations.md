# SketchyBar customizations (macOS / aerospace)

Notes on the bespoke changes layered on top of the FelixKratz SbarLua config.
Applied to **both** variants: `sketchybar/` and `sketchybar-docked/`
(`.config/sketchybar/...`). The live `~/.config/sketchybar` is a directory
symlink to the `sketchybar` variant, so editing it edits that variant directly.

Reload after any change: `sketchybar --reload`.

---

## 1. Far-left: focused workspace number (replaces the Apple logo)

**File:** `items/apple.lua`

The Apple-logo item was repurposed into a live indicator of the currently
focused aerospace workspace. It is a normal `item` whose `icon.string` is the
workspace number, updated on every workspace change.

Key pieces:

```lua
local focused_space = sbar.add("item", "focused_space", {
  icon = { font = { family = settings.font.numbers, size = 16.0 }, string = "1", ... },
  label = { drawing = false },
  background = { color = colors.bg2, border_color = colors.black, border_width = 1 },
  updates = true,
})

local function set_focused(n)
  n = (n or ""):gsub("%s+", "")
  if n ~= "" then focused_space:set({ icon = { string = n } }) end
end

-- live updates from the custom aerospace event (registered in init.lua)
focused_space:subscribe("aerospace_workspace_change", function(env)
  set_focused(env.FOCUSED_WORKSPACE)
end)

-- seed the value on load (the event only fires on change)
sbar.exec("aerospace list-workspaces --focused", function(result) set_focused(result) end)
```

Notes:
- `aerospace_workspace_change` is a custom event added in `init.lua`; aerospace
  triggers it via `exec-on-workspace-change` in `aerospace.toml`, passing
  `FOCUSED_WORKSPACE`.
- The init `sbar.exec("aerospace list-workspaces --focused", ...)` is required
  because the event does not fire at startup.
- The old `click_script` that opened the macOS menu was dropped (the menu-bar
  swap feature was removed earlier).

---

## 2. Front app: native icon in front of the app name

**File:** `items/front_app.lua`

A second `item` (`front_app.icon`) is added immediately before the existing
`front_app` name item. It draws the focused app's real macOS icon via the
built-in `background.image = "app.<App Name>"` source.

```lua
local front_app_icon = sbar.add("item", "front_app.icon", {
  display = "active",
  icon = { drawing = false }, label = { drawing = false },
  background = {
    color = colors.transparent, border_width = 0,
    image = { scale = 0.6, corner_radius = 5, drawing = true },
  },
  padding_left = 8, padding_right = 2, updates = true,
})

front_app:subscribe("front_app_switched", function(env)
  front_app:set({ label = { string = env.INFO } })
  front_app_icon:set({ background = { image = "app." .. env.INFO } })  -- native icon
end)
```

### The key SketchyBar fact (learned the hard way)

`background.image = "app.<App Name>"` loads the **real, full-color macOS app
icon**. This is the mechanism for native color icons anywhere in the bar
(verified with `sketchybar --query <item>` showing `image.value = "app.Warp"`).

**Caveat for multiple icons in one pill:** `background.image` does **not**
auto-size its item (unlike a text `icon`/`label`, which measures itself). With
`icon`/`label` disabled the box collapses to ~0 and the scaled image overflows
into its neighbor → overlap. So any row of native-icon items must set an
explicit `width` per item ≈ the rendered icon size (`scale * native`, roughly
~32px at `scale 0.66`). This is why the per-workspace app-icon row (in
`items/spaces.lua`) is a separate, still-in-progress effort: the original used
a single auto-sizing app-font *label*; native color icons require N fixed-width
image items instead.
