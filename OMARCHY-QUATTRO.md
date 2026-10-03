# Omarchy Quattro configuration

The current Linux desktop is saved in these packages:

- `hypr/.config/hypr`: Lua configuration, bindings, monitors and persistent workspaces.
- `omarchy/.config/omarchy`: shell layout, font settings, custom plugins, user themes, templates, hooks and extensions.
- `omarchy/.local/state/omarchy/toggles/hypr`: Hyprland overrides, including NVIDIA environment settings.
- `kitty`, `alacritty`, `ghostty` and `zsh`: terminal configuration and Linux shell settings.

The live directories are symlinks into this repository. Shell settings saved atomically also update the repository through these directory links. Stock files under `/usr/share/omarchy` and generated theme/cache files remain managed by Omarchy.

The saved bar has CPU, memory and temperature cards before the tray arrow, with the clock font and theme-based utilization colors. Spaces shows app icons and workspace numbers: 1/3/5 on DP-1 and 2/4/6 on DP-2. Adjust `hypr/.config/hypr/monitors.lua` when restoring to different hardware.

## Restore after reinstall

Install Omarchy Quattro first, then clone this repository and run:

```sh
git clone https://github.com/nsitapara/dotfiles.git ~/.dotfiles
~/.dotfiles/scripts/restore-omarchy --dry-run
~/.dotfiles/scripts/restore-omarchy
```

`./setup.sh --omarchy-only` runs the same restore. The helper backs up existing directories under `~/.local/state/dotfiles-backups/quattro/`, installs missing plugins at the recorded Git revisions, restores the theme, reloads Hyprland and restarts the shell. Run it from the desktop session. For restoration from a TTY, use `--no-reload --skip-theme` and select the saved theme after logging in.

The two custom plugins (`nsitapara.bar` and `nsitapara.system-monitor`) are tracked directly. Third-party plugin checkouts are ignored; their URLs and revisions are stored in `omarchy/.config/omarchy/plugins.lock.json`. Existing installed plugins are kept, including local changes or newer versions. Original bar/system-monitor plugins can remain installed while the saved layout uses the custom versions.

## Preserve later changes

After changing settings, installing/updating plugins, or changing the theme:

```sh
cd ~/.dotfiles
./scripts/restore-omarchy --snapshot
git status --short
git add hypr omarchy kitty alacritty ghostty zsh
git commit -m "Update Quattro desktop settings"
git push
```

Keep edits to third-party plugin source in a maintained fork or a separate tracked custom plugin. The snapshot command refuses dirty third-party checkouts so it cannot claim an upstream revision contains local edits. New custom plugin directories need an exception in `.gitignore` before being committed.

The old Linux Waybar package has been removed. The former theme package is now `themes-mac`, used only by the Mac setup; obsolete Hyprland/Waybar/Walker/Mako/SwayOSD theme files are removed. Quattro's active theme is generated in `~/.local/state/omarchy/current/theme`; custom templates follow theme changes automatically.

This preserves user configuration, not an entire OS image. Installed applications, services and hardware configuration are supplied by the Omarchy installation. Keep the repository pushed to GitHub or copied to another drive before reinstalling.
