-- Personal input overrides. These replace Omarchy's defaults.
-- See https://wiki.hypr.land/Configuring/Basics/Variables/#input

hl.config({
  input = {
    kb_layout = "us",

    -- Compose on Right Alt. NOTE: this replaces Omarchy's default
    -- "compose:caps,shift:both_capslock_cancel" wholesale.
    kb_options = "compose:ralt",

    -- Speed of keyboard repeat.
    repeat_rate = 40,
    repeat_delay = 600,

    -- Start with numlock on.
    numlock_by_default = true,

    -- Slow the mouse down and turn off acceleration.
    sensitivity = -0.4,
    accel_profile = "flat",

    touchpad = {
      -- Control the speed of scrolling.
      scroll_factor = 0.4,
    },
  },
})
