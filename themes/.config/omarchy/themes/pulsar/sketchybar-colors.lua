-- Pulsar theme colors for Sketchybar
-- Colors in 0xAARRGGBB format
-- Derived from: https://github.com/bjarneo/omarchy-pulsar-theme

return {
  black = 0xff0a0314,
  white = 0xffe0e6ff,
  red = 0xffe53e61,
  green = 0xff5cb960,
  blue = 0xff3298fa,
  yellow = 0xfff2e42e,
  orange = 0xffff5779,
  magenta = 0xffb82aff,
  cyan = 0xff3df2f2,
  mauve = 0xffb82aff,
  grey = 0xffaa5abc,
  transparent = 0x00000000,

  bar = {
    bg = 0xf00a0314,
    border = 0xff0a0314,
  },
  popup = {
    bg = 0xc00a0314,
    border = 0xffaa5abc
  },
  bg1 = 0xff1a0f24,
  bg2 = 0xff2a1f34,

  with_alpha = function(color, alpha)
    if alpha > 1.0 or alpha < 0.0 then return color end
    return (color & 0x00ffffff) | (math.floor(alpha * 255.0) << 24)
  end,
}
