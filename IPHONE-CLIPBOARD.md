# iPhone Clipboard Bridge

Copy and paste between an iPhone and a Linux (Hyprland/Wayland) machine with a
Back Tap on the iPhone. Mac ↔ iPhone and Mac ↔ Mac don't need this: Apple's
Universal Clipboard already covers them.

| Gesture on the iPhone | What it does |
|---|---|
| Double Tap | Sends the iPhone clipboard (text or image) to the Linux clipboard |
| Triple Tap | Copies the Linux clipboard (text) to the iPhone |

iOS never lets an app read the clipboard in the background, so one tap is as
close to seamless as an iPhone gets with a non-Apple machine.

## How it works

`setup.sh` writes a small Python HTTP server (`~/.local/bin/clip-bridge`) and a
systemd user service that starts it at login.

- `POST /clip` puts the request body in the Wayland clipboard (`wl-copy`) and
  shows a desktop notification.
- `GET /clip` returns the Wayland clipboard as text (`wl-paste`).
- Every request needs `Authorization: Bearer <token>`. The token is generated
  once into `~/.config/clip-bridge/token` (mode 600) and kept across re-runs.
- It listens on port `7655`. A ufw rule allows that port only on `tailscale0`,
  so the iPhone reaches it over Tailscale and nothing else on the network can.

## Linux setup

1. Install Tailscale and sign in (`tailscale up`).
2. In a terminal, run the following. It asks for your sudo password to add the
   ufw rule.

   ```sh
   ~/.dotfiles/setup.sh --clip-bridge-only
   ```

   A full `./setup.sh` run also asks whether you want the bridge. Set
   `WANT_CLIP_BRIDGE=1` or `0` to skip the question.
3. Note the two values printed at the end:

   ```
   Shortcut URL:   http://<machine>.<tailnet>.ts.net:7655/clip
   Shortcut token: Authorization: Bearer <token>
   ```

   To print the token again, run `cat ~/.config/clip-bridge/token`.
4. Check that it's running: `systemctl --user status clip-bridge`.

## iPhone setup

1. Install Tailscale from the App Store, sign in to the same tailnet and keep
   the VPN connected.
2. **Send to PC** shortcut (Shortcuts app → **+**):
   1. **Get Clipboard**
   2. **Get Contents of URL** set to the Shortcut URL. Under **Show More**:
      - Method: **POST**
      - Headers: `Authorization` = `Bearer <token>`
      - Request Body: **File** → **Clipboard**
3. **Get from PC** shortcut:
   1. **Get Contents of URL** with the same URL. Method **GET**, same header.
   2. **Set Clipboard** → *Contents of URL*
4. Run each shortcut once from the Shortcuts app. When iOS asks for clipboard
   access, choose **Always Allow**.
5. In **Settings → Accessibility → Touch → Back Tap**, set **Double Tap** to
   Send to PC and **Triple Tap** to Get from PC.

Shortcuts sync through iCloud, so other iPhones on the same Apple ID already
have them. For a new Linux machine, change the URL and token inside both
shortcuts.

## Troubleshooting

- **Nothing arrives:** check that Tailscale is connected on the iPhone, then
  check `systemctl --user status clip-bridge` and
  `journalctl --user -u clip-bridge` on Linux.
- **401 from the shortcut:** the header must be `Bearer`, one space, then the
  exact token.
- **Back Tap misses:** tap firmly near the Apple logo. Thick or rugged cases and
  MagSafe wallets make it unreliable.

## Removing it

```sh
WANT_CLIP_BRIDGE=0 ./setup.sh   # or answer "no" to the bridge prompt
sudo ufw delete allow in on tailscale0 to any port 7655 proto tcp
```

The token in `~/.config/clip-bridge/` is kept. Delete it to revoke the iPhone's
access for good.
