-- One Dark Pro theme colors for Sketchybar
-- Colors in 0xAARRGGBB format
-- Derived from: https://github.com/sc0ttman/omarchy-one-dark-pro-theme

return {
  black = 0xff282c34,
  white = 0xffabb2bf,
  red = 0xffe06c75,
  green = 0xff98c379,
  blue = 0xff61afef,
  yellow = 0xffe5c07b,
  orange = 0xffda6f3f,
  magenta = 0xffc678dd,
  cyan = 0xff56b6c2,
  mauve = 0xffc678dd,    -- Using magenta as mauve
  grey = 0xff5c6370,
  transparent = 0x00000000,

  bar = {
    bg = 0xf01e2229,
    border = 0xff1e2229,
  },
  popup = {
    bg = 0xc01e2229,
    border = 0xff5c6370
  },
  bg1 = 0xff282c34,
  bg2 = 0xff3e4451,

  with_alpha = function(color, alpha)
    if alpha > 1.0 or alpha < 0.0 then return color end
    return (color & 0x00ffffff) | (math.floor(alpha * 255.0) << 24)
  end,
}
