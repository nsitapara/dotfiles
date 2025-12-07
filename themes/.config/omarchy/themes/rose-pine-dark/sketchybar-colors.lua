-- Rose Pine Dark theme colors for Sketchybar
-- Colors in 0xAARRGGBB format
-- Derived from: https://github.com/guilhermetk/omarchy-rose-pine-dark

return {
  black = 0xff26233a,
  white = 0xffe0def4,
  red = 0xffeb6f92,
  green = 0xff31748f,
  blue = 0xff9ccfd8,
  yellow = 0xfff6c177,
  orange = 0xfff6c177,
  magenta = 0xffc4a7e7,
  cyan = 0xffebbcba,
  mauve = 0xffc4a7e7,
  grey = 0xff6e6a86,
  transparent = 0x00000000,

  bar = {
    bg = 0xf0191724,
    border = 0xff191724,
  },
  popup = {
    bg = 0xc0191724,
    border = 0xff6e6a86
  },
  bg1 = 0xff1f1d2e,
  bg2 = 0xff26233a,

  with_alpha = function(color, alpha)
    if alpha > 1.0 or alpha < 0.0 then return color end
    return (color & 0x00ffffff) | (math.floor(alpha * 255.0) << 24)
  end,
}
