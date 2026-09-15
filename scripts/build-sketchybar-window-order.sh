#!/bin/bash
# Build the temporary native ordering fix. No running service is changed.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-"$HOME/Applications/SketchyBar Window Order.app"}
if [[ -e "$output" ]]; then
  echo "Refusing to overwrite $output; rebuilding changes Accessibility identity." >&2
  exit 1
fi
work=$(mktemp -d "${TMPDIR:-/tmp}/sketchybar-order.XXXXXX")
trap 'rm -rf "$work"' EXIT
git clone --depth 1 --branch v2.24.0 https://github.com/FelixKratz/SketchyBar.git "$work/source"
[[ $(git -C "$work/source" rev-parse HEAD) == 6284ee816601486ace33ca48a0271832eec6de35 ]]
git -C "$work/source" apply --check "$root/sketchybar-patches/window-order.patch"
git -C "$work/source" apply "$root/sketchybar-patches/window-order.patch"
unset SDKROOT MACOSX_DEPLOYMENT_TARGET
export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)
case $(uname -m) in
  arm64) target=arm64 ;;
  x86_64) target=x86 ;;
  *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
make -C "$work/source" "$target" -j4
bundle="$work/SketchyBar Window Order.app"
mkdir -p "$bundle/Contents/MacOS"
install -m755 "$work/source/bin/sketchybar" "$bundle/Contents/MacOS/sketchybar"
cp "$root/sketchybar-patches/Info.plist" "$bundle/Contents/Info.plist"
codesign --force --sign - --identifier local.dotfiles.sketchybar-window-order "$bundle/Contents/MacOS/sketchybar"
codesign --force --sign - "$bundle"
codesign --verify --deep --strict "$bundle"
mkdir -p "$(dirname "$output")"
mv "$bundle" "$output"
printf 'Built %s\n' "$output"
