# Theme System - Claude Instructions

This document describes how to create macOS-specific theme configurations when adding a new Omarchy theme.

## Overview

The theme system uses Omarchy's structure with added macOS-specific extensions:

```
~/.config/omarchy/themes/<theme-name>/
├── alacritty.toml      # FROM OMARCHY (cross-platform)
├── neovim.lua          # FROM OMARCHY (cross-platform)
├── backgrounds/        # Wallpapers
└── macos/              # OUR macOS ADDITIONS
    ├── sketchybar-colors.lua
    ├── kitty.conf
    ├── ghostty.conf
    ├── borders.sh
    ├── eza-theme.yml
    ├── fzf-colors.sh
    └── starship-palette.txt
```

## When Adding a New Theme

1. Download the Omarchy theme to `~/dotfiles/themes/.config/omarchy/themes/<name>/`
2. Create the `macos/` subdirectory
3. Extract colors from `alacritty.toml` (primary source of truth)
4. Generate each macOS config file using the templates below

## Extracting Colors from alacritty.toml

The alacritty.toml contains the canonical color definitions:

```toml
[colors.primary]
foreground = "#abb2bf"
background = "#1e2229"

[colors.normal]
black   = "#282c34"
red     = "#e06c75"
green   = "#98c379"
yellow  = "#e5c07b"
blue    = "#61afef"
magenta = "#c678dd"
cyan    = "#56b6c2"
white   = "#abb2bf"

[colors.bright]
# Usually same or slightly brighter variants

[colors.selection]
background = "#3e4451"  # Used for bg2, highlights
```

## Color Format Conversion

| Format | Example | Used By |
|--------|---------|---------|
| `#RRGGBB` | `#61afef` | kitty, eza, fzf |
| `0xAARRGGBB` | `0xff61afef` | sketchybar, borders |
| `RRGGBB` (no #) | `61afef` | ghostty |

### Hex to Sketchybar/Borders (0xAARRGGBB)

For fully opaque colors: `#RRGGBB` → `0xffRRGGBB`
For transparency: Use `0xAAxxxxxx` where AA is alpha (00=transparent, ff=opaque)

Example: `#61afef` → `0xff61afef`

---

## Template: sketchybar-colors.lua

```lua
-- <Theme Name> theme colors for Sketchybar
-- Colors in 0xAARRGGBB format
-- Derived from: <source URL>

return {
  black = 0xff<black>,
  white = 0xff<foreground>,
  red = 0xff<red>,
  green = 0xff<green>,
  blue = 0xff<blue>,
  yellow = 0xff<yellow>,
  orange = 0xff<orange or yellow variant>,
  magenta = 0xff<magenta>,
  cyan = 0xff<cyan>,
  mauve = 0xff<magenta>,    -- Use magenta if no mauve
  grey = 0xff<dim/grey color>,
  transparent = 0x00000000,

  bar = {
    bg = 0xf0<background>,   -- f0 = slight transparency
    border = 0xff<background>,
  },
  popup = {
    bg = 0xc0<background>,   -- c0 = more transparency
    border = 0xff<grey>
  },
  bg1 = 0xff<selection bg>,
  bg2 = 0xff<slightly lighter selection>,

  with_alpha = function(color, alpha)
    if alpha > 1.0 or alpha < 0.0 then return color end
    return (color & 0x00ffffff) | (math.floor(alpha * 255.0) << 24)
  end,
}
```

---

## Template: kitty.conf

```conf
# <Theme Name> Theme for Kitty
# Derived from: <source URL>

## Primary colors
foreground              #<foreground>
background              #<background>
selection_foreground    #<foreground>
selection_background    #<selection>

## Cursor
cursor                  #<foreground>
cursor_text_color       #<background>

## URL
url_color               #<blue>

## Borders
active_border_color     #<blue>
inactive_border_color   #<grey>
bell_border_color       #<yellow>

## Tabs
active_tab_foreground   #<background>
active_tab_background   #<blue>
inactive_tab_foreground #<foreground>
inactive_tab_background #<dim background>
tab_bar_background      #<background>

## Marks
mark1_foreground #<background>
mark1_background #<blue>
mark2_foreground #<background>
mark2_background #<magenta>
mark3_foreground #<background>
mark3_background #<cyan>

## ANSI colors
# black
color0 #<black>
color8 #<bright black>

# red
color1 #<red>
color9 #<red>

# green
color2  #<green>
color10 #<green>

# yellow
color3  #<yellow>
color11 #<yellow>

# blue
color4  #<blue>
color12 #<blue>

# magenta
color5  #<magenta>
color13 #<magenta>

# cyan
color6  #<cyan>
color14 #<cyan>

# white
color7  #<white>
color15 #<bright white>
```

---

## Template: ghostty.conf

```conf
# <Theme Name> Theme for Ghostty
# Derived from: <source URL>

background = <background without #>
foreground = <foreground without #>
selection-background = <selection without #>
selection-foreground = <foreground without #>
cursor-color = <foreground without #>

# ANSI colors
palette = 0=#<black>
palette = 1=#<red>
palette = 2=#<green>
palette = 3=#<yellow>
palette = 4=#<blue>
palette = 5=#<magenta>
palette = 6=#<cyan>
palette = 7=#<white>
palette = 8=#<bright black>
palette = 9=#<red>
palette = 10=#<green>
palette = 11=#<yellow>
palette = 12=#<blue>
palette = 13=#<magenta>
palette = 14=#<cyan>
palette = 15=#<bright white>
```

---

## Template: borders.sh

```bash
#!/bin/bash
# <Theme Name> theme colors for JankyBorders (Aerospace)
# Colors in 0xAARRGGBB format
# Derived from: <source URL>

export BORDER_ACTIVE="0xff<accent color, usually blue/magenta>"
export BORDER_INACTIVE="0xff<grey>"
export BORDER_WIDTH="8.0"
```

---

## Template: fzf-colors.sh

```bash
#!/bin/bash
# <Theme Name> theme colors for FZF
# Derived from: <source URL>

export FZF_DEFAULT_OPTS=" \
--color=bg+:#<selection>,bg:#<background>,spinner:#<yellow>,hl:#<red> \
--color=fg:#<foreground>,header:#<red>,info:#<magenta>,pointer:#<yellow> \
--color=marker:#<blue>,fg+:#<bright foreground>,prompt:#<magenta>,hl+:#<red> \
--color=selected-bg:#<selection> \
--color=border:#<grey>,label:#<foreground>"
```

---

## Template: eza-theme.yml

This is the most complex file. Key color mappings:

| Category | Colors to use |
|----------|---------------|
| filekinds.directory | blue |
| filekinds.symlink | cyan |
| filekinds.executable | green |
| perms.read | red |
| perms.write | yellow |
| perms.execute | green |
| git.new | green |
| git.modified | yellow |
| git.deleted | red |
| file_type.source | blue |
| file_type.image | yellow |
| file_type.video | red |

See existing themes for full structure. Copy `catppuccin-mocha/macos/eza-theme.yml` as base and replace colors.

---

## Template: starship-palette.txt

This file contains just the palette name for starship. The theme CLI reads this file and updates the `palette = 'xxx'` line in `~/.config/starship.toml`.

**Important:** The palette name must match a `[palettes.xxx]` section in starship.toml. When adding a new theme, you must also add the corresponding palette definition to `~/dotfiles/starship/.config/starship.toml`.

```
<palette_name>
```

Examples:
- `catppuccin_mocha`
- `one_dark_pro`
- `gruvbox_dark`

---

## Adding a New Theme - Step by Step

1. **Clone the Omarchy theme:**
   ```bash
   cd ~/dotfiles/themes/.config/omarchy/themes
   git clone <repo-url> <theme-name>
   ```

2. **Create macos directory:**
   ```bash
   mkdir -p <theme-name>/macos
   ```

3. **Extract colors from alacritty.toml:**
   - Open `<theme-name>/alacritty.toml`
   - Note: background, foreground, all ANSI colors, selection

4. **Create each macOS config file** using templates above

5. **Re-stow themes:**
   ```bash
   cd ~/dotfiles && stow -R themes
   ```

6. **Test the theme:**
   ```bash
   theme switch <theme-name>
   ```

---

## Testing Checklist

After creating a new theme, verify:

- [ ] `theme switch <name>` runs without errors
- [ ] Sketchybar colors update
- [ ] Kitty colors update (SIGUSR1 reload)
- [ ] JankyBorders colors update
- [ ] FZF colors show correctly in new terminal
- [ ] `eza --icons` shows correct colors
- [ ] Ghostty colors work (after restart)

---

## Reference: Catppuccin Mocha Colors

As a reference, here are the Catppuccin Mocha colors:

| Name | Hex | Use |
|------|-----|-----|
| Base | #1e1e2e | Background |
| Text | #cdd6f4 | Foreground |
| Surface0 | #313244 | Selection |
| Surface2 | #585b70 | Grey |
| Red | #f38ba8 | Errors, red |
| Green | #a6e3a1 | Success, green |
| Yellow | #f9e2af | Warnings |
| Blue | #89b4fa | Info, links |
| Mauve | #cba6f7 | Accent |
| Pink | #f5c2e7 | Magenta |
| Teal | #94e2d5 | Cyan |

---

## Reference: One Dark Pro Colors

| Name | Hex | Use |
|------|-----|-----|
| Background | #1e2229 | Background |
| Foreground | #abb2bf | Foreground |
| Selection | #3e4451 | Selection |
| Grey | #5c6370 | Dim/grey |
| Red | #e06c75 | Errors |
| Green | #98c379 | Success |
| Yellow | #e5c07b | Warnings |
| Blue | #61afef | Info, links |
| Magenta | #c678dd | Accent |
| Cyan | #56b6c2 | Cyan |
