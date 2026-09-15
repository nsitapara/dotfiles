#!/bin/bash
# Build the reviewed, pinned macOS 27 workaround without changing the live service.
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
revision=dd845723416f5fe92af49fad5ebab00369e07edd
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/yabai-macos27.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT
output=${1:-"$HOME/Applications/Yabai macOS 27.app"}

if [[ -e "$output" ]]; then
    echo "Output already exists: $output. Choose a different path to preserve the running build and its Accessibility approval." >&2
    exit 1
fi
git init -q "$build_dir/source"
git -C "$build_dir/source" fetch -q --depth=1 https://github.com/asmvik/yabai.git "$revision"
git -C "$build_dir/source" checkout -q --detach FETCH_HEAD
git -C "$build_dir/source" apply "$repo_dir/yabai-patches/macos27.patch"
make -C "$build_dir/source" install

# Exercise serialization without sending any desktop-switching events.
xcrun clang -std=c11 -g -fsanitize=undefined \
    -I "$build_dir/source/src" "$repo_dir/tests/test_yabai_gesture.c" \
    -framework ApplicationServices -o "$build_dir/test-gesture"
"$build_dir/test-gesture"

mkdir -p "$build_dir/Yabai macOS 27.app/Contents/MacOS"
cp "$build_dir/source/bin/yabai" "$build_dir/Yabai macOS 27.app/Contents/MacOS/yabai"
cp "$repo_dir/yabai-patches/Info.plist" "$build_dir/Yabai macOS 27.app/Contents/Info.plist"
codesign --force --sign - --identifier local.dotfiles.yabai-macos27 "$build_dir/Yabai macOS 27.app"
codesign --verify --strict "$build_dir/Yabai macOS 27.app"
mkdir -p "$(dirname "$output")"
mv "$build_dir/Yabai macOS 27.app" "$output"
"$output/Contents/MacOS/yabai" --version
echo "Built: $output"
echo "Grant this app Device Control and Data Access before activating it. See yabai-patches/README.md."
