#!/bin/bash
# PostToolUse hook (Edit|Write|MultiEdit): open the file Claude just edited in your IDE,
# inside the correct PROJECT window so the Explorer is populated and you can navigate.
#
# CodeNexus sets two env vars per-session from its app settings (Settings → External Apps):
#
#   CODENEXUS_OPEN_EDITED_IN_EDITOR — view mode:
#     off (default / unset)  — do nothing. This is the default when the var is unset, so
#                              Claude sessions NOT launched by CodeNexus never auto-open
#                              an editor.
#     diff                   — side-by-side DIFF of the file's git HEAD version vs the
#                              current working copy (same as the Source Control panel —
#                              the full uncommitted change, not just the last edit).
#     file                   — just open/focus the file, no diff (quieter).
#
#   CODENEXUS_OPEN_EDITED_CMD — editor command (e.g. cursor, code, pycharm, zed).
#                              Empty → auto-detect the first available of the above.
#
# Project-window targeting: the file's git worktree root is passed as a folder argument so
# VS Code-family editors route to the window that already has that worktree open (loading
# the Explorer), instead of dropping the file into whichever window was last active. With
# multiple worktrees open in separate windows, each edit lands in its own project's window.
# Editors:
#   VS Code family (cursor, code, code-insiders, codium) — `<bin> <root> --goto/--diff …`
#   JetBrains family (pycharm, idea, …) — `<bin> diff L R` / `<bin> FILE` (project resolved
#                                          from the file path by the IDE itself)
#   Anything else — best-effort open of the file (no diff).
#
# Outside CodeNexus both vars are unset, so the default mode is `off` and the hook does
# nothing. For new/untracked files (no HEAD version) `diff` falls back to just opening the
# file. Convenience hook only — does NOT change permission mode.

mode=${CODENEXUS_OPEN_EDITED_IN_EDITOR:-off}
[ "$mode" = "off" ] && exit 0

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

[ -z "$file" ] && exit 0
[ -f "$file" ] || exit 0

# Resolve the editor command: explicit setting, else auto-detect.
editor=${CODENEXUS_OPEN_EDITED_CMD:-}
if [ -z "$editor" ]; then
  for cand in cursor code pycharm zed; do
    command -v "$cand" >/dev/null 2>&1 && { editor="$cand"; break; }
  done
fi
[ -z "$editor" ] && exit 0

# Project root for the edited file (its git worktree root). Used both to target the right
# editor window/workspace and, in diff mode, to locate the HEAD version.
repo=$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null)

# Classify the editor by its first token's basename to pick the right CLI syntax. When the
# project root is known, VS Code-family commands lead with "$repo" so the file opens in
# that workspace's window (Explorer loaded); otherwise they fall back to --reuse-window.
editor_base=$(basename "$(printf '%s' "$editor" | awk '{print $1}')")

case "$editor_base" in
  cursor|code|code-insiders|codium|vscodium)
    if [ -n "$repo" ]; then
      open_file() { $editor "$repo" --goto "$1" >/dev/null 2>&1 & }
      open_diff() { $editor "$repo" --diff "$1" "$2" >/dev/null 2>&1 & }
    else
      open_file() { $editor --reuse-window --goto "$1" >/dev/null 2>&1 & }
      open_diff() { $editor --reuse-window --diff "$1" "$2" >/dev/null 2>&1 & }
    fi
    ;;
  pycharm|charm|idea|webstorm|goland|clion|rubymine|phpstorm|rider|datagrip|fleet)
    open_file() { $editor "$1" >/dev/null 2>&1 & }
    open_diff() { $editor diff "$1" "$2" >/dev/null 2>&1 & }
    ;;
  *)
    # Unknown editor: open the file; no reliable two-file diff CLI, so diff falls back.
    open_file() { $editor "$1" >/dev/null 2>&1 & }
    open_diff() { open_file "$2"; }
    ;;
esac

# 'file' mode: just open the file (in its project window), no diff.
if [ "$mode" = "file" ]; then
  open_file "$file"
  exit 0
fi

# 'diff' mode (default): side-by-side HEAD vs working copy.
if [ -z "$repo" ]; then
  open_file "$file"
  exit 0
fi
rel=${file#"$repo"/}

# Materialize the HEAD version into a stable temp path (preserving the filename so the
# editor shows syntax highlighting and a sensible diff title).
base_dir="/tmp/claude-head-versions"
mkdir -p "$base_dir"
head_copy="$base_dir/$(printf '%s' "$rel" | tr '/' '_')"

if git -C "$repo" show "HEAD:$rel" > "$head_copy" 2>/dev/null; then
  open_diff "$head_copy" "$file"
else
  # No committed version (new/untracked file) — just open it.
  rm -f "$head_copy"
  open_file "$file"
fi

exit 0
