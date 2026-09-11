#!/usr/bin/env bash
# Shared bootstrap inputs; named SQL checkpoints stay in each worktree.
set -euo pipefail

main_worktree="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
worktree_root="$(git rev-parse --show-toplevel)"
[ "$worktree_root" != "$main_worktree" ] || exit 0

cache_dir="${DB_CACHE_DIR:-$HOME/.herasight-db-cache}"
mkdir -p "$cache_dir"

for name in db.sql.gz .db-cache; do
    case "$name" in
        db.sql.gz) shared_source="$main_worktree/db.sql.gz" ;;
        .db-cache) shared_source="$cache_dir" ;;
    esac
    target="$worktree_root/$name"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        ln -s "$shared_source" "$target"
    fi
    case "$name" in
        db.sql.gz) echo "Production dump input: $target" ;;
        .db-cache) echo "Shared just dev cache: $target -> $shared_source" ;;
    esac
done

# Preserve shared files while detaching legacy checkpoint links.
python3 - "$worktree_root" <<'CHECKPOINTS'
from pathlib import Path
import sys

root = Path(sys.argv[1])
directory = root / '.db-snapshots'
if directory.is_symlink():
    previous = directory.readlink()
    shared = directory.resolve()
    directory.unlink()
    try:
        directory.mkdir(mode=0o700)
    except BaseException:
        if not directory.exists():
            directory.symlink_to(previous)
        raise
    print(f'Previous shared checkpoints remain at {shared}')
directory.mkdir(mode=0o700, exist_ok=True)
print(f'Worktree SQL checkpoints: {directory}')
CHECKPOINTS
