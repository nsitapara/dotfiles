-- Catppuccin Latte theme colors for Sketchybar
-- Colors in 0xAARRGGBB format
-- Derived from: https://github.com/basecamp/omarchy/tree/master/themes/catppuccin-latte

return {
  black = 0xffbcc0cc,
  white = 0xff4c4f69,
  red = 0xffd20f39,
  green = 0xff40a02b,
  blue = 0xff1e66f5,
  yellow = 0xffdf8e1d,
  orange = 0xfffe640b,
  magenta = 0xffea76cb,
  cyan = 0xff179299,
  mauve = 0xff8839ef,
  grey = 0xff6c6f85,
  transparent = 0x00000000,

  bar = {
    bg = 0xf0eff1f5,
    border = 0xffeff1f5,
  },
  popup = {
    bg = 0xc0eff1f5,
    border = 0xff6c6f85
  },
  bg1 = 0xffccd0da,
  bg2 = 0xffbcc0cc,

  with_alpha = function(color, alpha)
    if alpha > 1.0 or alpha < 0.0 then return color end
    return (color & 0x00ffffff) | (math.floor(alpha * 255.0) << 24)
  end,
}
