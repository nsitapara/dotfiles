-- Personal keybinding overrides. Omarchy's defaults load first, so any key
-- that Omarchy already claims must be unbound before it can be rebound.
--
-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- ── Rebind keys Omarchy claims for something else ──────────────────────────

hl.unbind("SUPER + SHIFT + B") -- Omarchy default: Browser
o.bind("SUPER + SHIFT + B", "Zen Browser", { launch = "zen-browser" })

hl.unbind("SUPER + SHIFT + ALT + B") -- Omarchy default: default browser (chromium)
o.bind("SUPER + SHIFT + ALT + B", "Browser (private)", { launch = "google-chrome-stable --incognito" })

hl.unbind("SUPER + SHIFT + G") -- Omarchy default: Signal
o.bind("SUPER + SHIFT + G", "GitHub Desktop", { launch = "github-desktop", focus = "github desktop" })

hl.unbind("SUPER + SHIFT + W") -- Omarchy default: Omawrite
o.bind("SUPER + SHIFT + W", "Typora", { launch = "typora --enable-wayland-ime" })

hl.unbind("SUPER + SHIFT + S") -- Omarchy default: Google Maps
o.bind("SUPER + SHIFT + S", "Slack", { launch = "slack" })

hl.unbind("SUPER + SHIFT + P") -- Omarchy default: Google Photos
o.bind("SUPER + SHIFT + P", "PyCharm", { launch = "pycharm" })

-- ── Keys Omarchy leaves free ───────────────────────────────────────────────

-- Omarchy puts Activity on SUPER + CTRL + T; keep it on SUPER + SHIFT + T too.
o.bind("SUPER + SHIFT + T", "Activity", { tui = "btop" })

-- macOS-style drag-a-box screenshot (like Shift + Cmd + 4). Saves a PNG to
-- Pictures, copies it to the clipboard, and shows a notification you can click
-- to open the editor. Press again mid-selection to cancel.
o.bind("SHIFT + ALT + 4", "Screenshot (region)", "omarchy-capture-screenshot region")

-- ── Already covered by Omarchy's defaults (kept here as a record) ───────────
--
-- These were in the old bindings.conf and are NOT lost -- Omarchy Quattro now
-- binds each of them to the same key with equivalent behaviour, so redefining
-- them would only add drift:
--
--   SUPER + RETURN            Terminal (omarchy-launch-terminal already opens in cwd)
--   SUPER + SHIFT + F         File manager (already nautilus --new-window)
--   SUPER + SHIFT + M         Music (spotify)
--   SUPER + SHIFT + ALT + M   Music TUI (cliamp, focus)
--   SUPER + SHIFT + N         Editor
--   SUPER + SHIFT + D         Docker (lazydocker)
--   SUPER + SHIFT + O         Obsidian (focus ^obsidian$)
--   SUPER + SHIFT + ALT + A   Grok
--   SUPER + SHIFT + Y         YouTube
--   SUPER + SHIFT + ALT + G   WhatsApp (focus)
--   SUPER + SHIFT + CTRL + G  Google Messages (focus)
