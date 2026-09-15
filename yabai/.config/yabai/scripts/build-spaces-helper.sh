#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/Dotfiles Spaces.app"
SOURCE="$HERE/helpers/Spaces.swift"
BINARY="$APP/Contents/MacOS/Dotfiles Spaces"
if [ -x "$BINARY" ] && [ "$BINARY" -nt "$SOURCE" ]; then exit 0; fi
command -v swiftc >/dev/null || { echo 'Install Xcode Command Line Tools to build the desktop helper.' >&2; exit 1; }
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>local.dotfiles.spaces</string>
<key>CFBundleName</key><string>Dotfiles Spaces</string>
<key>CFBundleExecutable</key><string>Dotfiles Spaces</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSUIElement</key><true/>
</dict></plist>
EOF
# The toolchain's default deployment target can exceed the running OS, and
# LaunchServices then refuses to open the app (error -10825). Pin it.
swiftc -O -target "$(uname -m)-apple-macos13.0" "$SOURCE" -o "$BINARY" -framework AppKit -framework ApplicationServices
codesign --force --sign - --identifier local.dotfiles.spaces "$APP"
