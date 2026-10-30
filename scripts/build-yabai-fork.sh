#!/bin/bash
# Build the pinned nsitapara/yabai fork into an app bundle without changing the live service.
set -euo pipefail
# Keep the SDK paired with xcrun's selected toolchain when CLT and Xcode differ.
export SDKROOT="${SDKROOT:-$(xcrun --sdk macosx --show-sdk-path)}"

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
repository=https://github.com/nsitapara/yabai.git
revision=a6a9fb46802ac9e584227f192d496f8f12a3bd98
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/yabai-fork.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT
output=${1:-"$HOME/Applications/Yabai Fork.app"}

if [[ -e "$output" ]]; then
    echo "Output already exists: $output. Choose a different path to preserve the running build and its Accessibility approval." >&2
    exit 1
fi
git init -q "$build_dir/source"
git -C "$build_dir/source" fetch -q --depth=1 "$repository" "$revision"
git -C "$build_dir/source" checkout -q --detach FETCH_HEAD

# The fork's own checks compile real sources against stubs and post no events.
# Its tests/bin suite drives the live desktop, so it is never run here.
"$build_dir/source/tests/local/run.sh"
# Serial: make -j races on the shared scripting-addition recipe.
make -C "$build_dir/source" install

mkdir -p "$build_dir/Yabai Fork.app/Contents/MacOS"
cp -X "$build_dir/source/bin/yabai" "$build_dir/Yabai Fork.app/Contents/MacOS/yabai"
cp "$repo_dir/yabai-fork/Info.plist" "$build_dir/Yabai Fork.app/Contents/Info.plist"
# make install's icon step leaves resource-fork attributes that ad-hoc signing rejects.
xattr -cr "$build_dir/Yabai Fork.app"
codesign --force --sign - --identifier local.dotfiles.yabai-fork "$build_dir/Yabai Fork.app"
codesign --verify --strict "$build_dir/Yabai Fork.app"
mkdir -p "$(dirname "$output")"
mv "$build_dir/Yabai Fork.app" "$output"
"$output/Contents/MacOS/yabai" --version
echo "Built: $output"
echo "Grant this app Device Control and Data Access before activating it. See yabai-fork/README.md."
