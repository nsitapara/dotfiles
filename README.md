# Dotfiles

Personal Linux and macOS settings.

For the current Omarchy Quattro desktop, see [restore instructions](OMARCHY-QUATTRO.md). Run `./setup.sh --omarchy-only` to restore just the saved desktop configuration.

The full `./setup.sh` installs platform dependencies, links shared dotfiles and offers machine-specific setup. macOS uses the separate `themes-mac` and SketchyBar packages.

## Window manager alternatives

Yabai is the Mac window manager. The monitor menu's **Yabai** section has
**Restart**, which rediscovers every window (use it when an app looks floating
but won't tile, or its bar icon is missing) and starts yabai after a quit, and
**Quit**, which stops yabai and skhd and leaves apps open. AeroSpace's config is
kept; `./wm.sh use aerospace` still switches to it from a terminal.
