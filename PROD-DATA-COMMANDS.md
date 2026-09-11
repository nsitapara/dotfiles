# Local database commands

The `zsh-mac` Stow package installs these helpers under
`~/.config/herasight/`. Its `.zshrc` loads their shell functions.
For an already-open terminal, load them with:

```zsh
source ~/.config/herasight/db_snapshot.zsh
```

## Build the shared baseline

Run `prod_build` from any directory. It restores
`~/Documents/web-platform/db.sql.gz` into isolated temporary Postgres,
builds `herasight-db:prod-baseline`, and removes the temporary resources.
It leaves existing development databases alone.

Each invocation restores and rebuilds, even when the dump is unchanged.
The fixed tag is replaced only after the restore and build succeed.
Older images are removed when unused; images referenced by containers and
Docker build caches may remain. The source dump is retained.

Long steps report elapsed time every ten seconds. Compression also reports
the archive size, and a successful build prints its total duration.

## Use or remove production data

Keep your frontend session running. In another terminal, enter the main
checkout or a feature worktree and run:

```zsh
prod_seed
```

This replaces that checkout's database and Redis cache with the shared
production baseline, applies migrations automatically, and restarts only
the backend on its existing ports. It does not launch frontends.

To return to development data, run:

```zsh
prod_remove
```

This removes the local Compose image override and follows the cache and
bootstrap workflow for `just dev --report 0`: restore the matching cached
database, or bootstrap and cache it if absent, then run the branch seed.
It preserves frontend processes and backend ports.

Both commands discard the target checkout's current database and cache.
They verify that its Compose containers belong to that checkout.
The worktree must have its normal environment setup and backend ports
initialized, for example by an earlier `just start` or `just dev`.

## Requirements and verification

The helpers use Python 3, Docker, Just, gzip, and the web-platform repository
scripts. The main checkout path is configured by `MAIN` in `db_snapshot.py`.

Run the isolated unit tests:

```sh
python3 ~/.config/herasight/test_db_snapshot.py
```

The Docker integration test builds a separate image from a tiny synthetic
dump, verifies restored rows and failed-restore protection, and cleans up:

```sh
python3 ~/.config/herasight/test_db_snapshot_docker.py
```

Production dumps, Docker images, environment files, and restore logs are
local runtime data and are not part of the dotfiles repository.

## Worktree SQL checkpoints

Run these from any subdirectory of a configured web-platform checkout:

```zsh
save_snapshot before-edit
list_snapshots
load_snapshot before-edit
```

`save_snapshot` without a name generates a branch-based name such as
`my-branch-1`. `load_snapshot` without a name selects the most recently
saved SQL archive in this checkout. `list_snapshot` is also accepted.
Saving an existing name replaces that checkpoint only after a successful
dump and metadata write. Failed saves preserve the previous checkpoint.

Every checkpoint is a full gzip-compressed SQL dump, plus the existing
Just migration metadata. Files live in `<worktree>/.db-snapshots/` and are
excluded from Git. If worktree setup linked this directory to the main
checkout, the first command replaces only that symlink with a private
directory. Existing snapshots remain in the original shared directory. A shared `DB_SNAPSHOTS_DIR` setting is ignored by these
shell helpers. Switching branches within one checkout retains its
checkpoints; a separate worktree has separate checkpoints. Deleting the
worktree also deletes its checkpoint directory.

Saving leaves the stack running. Loading validates the archive and
migration compatibility, stops this checkout's API and Celery, replaces
its database, clears its Redis cache, runs migrations automatically, and
starts its backend on the existing ports. Frontend processes keep running.
The production-image override, if installed, is retained. Checkpoints do
not include Redis, uploaded files, external services, or code changes.

Changed migration files require `load_snapshot NAME --force`, matching
the Just policy. Missing migration files and metadata errors block the
restore even with force. A failed SQL restore or migration leaves API and
Celery stopped so you can fix the error and retry. Restore error details
are saved privately in `.db-snapshots/.restore.log`.

The shell layer reuses `just save-snapshot`, `just list-snapshots`, and
`scripts/check_snapshot_compat.py`. It performs the SQL restore with
strict error handling and backend coordination instead of calling the
uncoordinated `just load-snapshot` recipe. Commands in the same worktree
are locked against concurrent snapshot saves or loads.

Run the SQL checkpoint integration test with:

```sh
python3 ~/.config/herasight/test_sql_snapshots_docker.py
```

It saves and restores synthetic rows using real Postgres and the Just
recipes, verifies Redis clearing and SQL failure handling, and checks
that existing Compose stacks stayed unchanged. Django migration calls
are mocked in this fixture; unit tests check their invocation and ordering.

## Worktree creation

`~/.config/herasight/link-worktree-db.sh` is the database setup hook shared
by the local T3, gtr, and CodeNexus entry points. It links `db.sql.gz` to
the main production dump and `.db-cache` to the shared development cache,
then creates a private `.db-snapshots/` directory in the new worktree.
Existing checkpoint symlinks are detached without deleting shared files.

The console labels `.db-cache` as the shared `just dev` cache and
`.db-snapshots` as worktree SQL checkpoints. Cache keys, cached files,
and the `just dev --report 0` cache-hit workflow are unchanged.
