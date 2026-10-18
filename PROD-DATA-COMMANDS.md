# Local database commands

The `zsh-mac` Stow package installs `~/.config/herasight/db_snapshot.zsh`,
and its `.zshrc` loads it. Each shell function in it calls pilotcli
(`~/.local/bin/pilotcli`, from `~/Documents/GitHub/pilotCLI`). For an
already-open terminal, load them with:

```zsh
source ~/.config/herasight/db_snapshot.zsh
```

| Function | pilotcli command |
|---|---|
| `prod_build [--native\|--docker]` | `env create-baseline --project web-platform --backend available\|native\|docker` |
| `prod_seed` | `env update-db -C "$PWD" --source prod` |
| `prod_remove` | `env update-db -C "$PWD" --source dev` |
| `save_snapshot [name]` | `env create-snapshot -C "$PWD" [name]` |
| `list_snapshots` (or `list_snapshot`) | `env list-snapshots -C "$PWD"` |
| `load_snapshot [name] [--force]` | `env update-db -C "$PWD" --source snapshot [--snapshot name] [--force true]` |

Every function passes `-C "$PWD"`, so it acts on the checkout you are in,
never on `$PILOT_WORKTREE_PATH`'s. Each prints its progress and closing line
as text (`--format text`).

## Build the shared baseline

Run `prod_build` from any directory. It restores the main checkout's
`db.sql.gz` into an isolated temporary Postgres and publishes the result. It
leaves existing development databases alone. By default it builds each
backend that is available:

- **native:** a Postgres 17 cluster under `~/.local/share/herasight/prod-baseline`;
- **Docker:** the image `herasight-db:prod-baseline`, when Docker answers.

`prod_build --native` or `prod_build --docker` builds one. Each invocation
restores and rebuilds, even when the dump is unchanged. The baseline is
replaced only after the restore and build succeed, and the source dump is
kept. Long steps report elapsed time every ten seconds, and a successful
build prints its total duration.

## Use or remove production data

Keep your frontend session running. In another terminal, enter the main
checkout or a feature worktree and run:

```zsh
prod_seed
```

This replaces that checkout's database and Redis cache with the production
baseline, on the backend the checkout runs (native stack or Docker), applies
migrations automatically, and restarts only the backend on its existing
ports. It does not launch frontends.

To return to development data, run:

```zsh
prod_remove
```

This removes the production baseline from the checkout and follows the
cache and bootstrap workflow for `just dev --report 0`: restore the matching
cached database, or bootstrap and cache it if absent, then run the branch
seed. It preserves frontend processes and backend ports.

Both commands discard the target checkout's current database and cache.
They verify that the backend they replace belongs to that checkout. The
worktree must have its normal environment setup and backend ports
initialized, for example by an earlier `just ndev`/`just nstart` (or `just
dev`/`just start` on Docker).

## Configuration and tests

pilotcli reads the facts from `~/.config/pilotcli/config.toml`:
`main_checkout` under `[projects.web-platform]`, and `prod_dump`,
`db_cache`, `prod_baseline`, `prod_image` and `pg_bin` under
`[projects.web-platform.env]`.

The tests live in pilotCLI:

```sh
cd ~/Documents/GitHub/pilotCLI
go test ./internal/devdb/ ./internal/modules/env/   # unit tests
make live-env   # a throwaway native stack: a test run and a checkpoint round trip
make live-db    # the baseline builders, native and Docker, on a tiny synthetic dump
```

The two `make live-*` tests start real stacks; run them deliberately.

Production dumps, baselines, Docker images, environment files, and restore
logs are local runtime data and are not part of the dotfiles repository.

## Worktree SQL checkpoints

Run these from any subdirectory of a configured web-platform checkout:

```zsh
save_snapshot before-edit
list_snapshots
load_snapshot before-edit
```

`save_snapshot` without a name generates a branch-based name such as
`my-branch-1`. `load_snapshot` without a name selects the most recently
saved SQL archive in this checkout. Saving an existing name replaces that
checkpoint only after a successful dump and metadata write. Failed saves
preserve the previous checkpoint. A checkout holding production data from
`prod_seed` refuses to save.

Every checkpoint is a full gzip-compressed SQL dump, plus the existing
Just migration metadata. Files live in `<worktree>/.db-snapshots/` (private,
0700) and are excluded from Git. Switching branches within one checkout
retains its checkpoints; a separate worktree has separate checkpoints.
Deleting the worktree also deletes its checkpoint directory.

Saving leaves the stack running. Loading validates the archive and
migration compatibility, stops this checkout's API and Celery, replaces
its database, clears its Redis cache, runs migrations automatically, and
starts its backend on the existing ports. Frontend processes keep running.
Checkpoints do not include Redis, uploaded files, external services, or
code changes.

Changed migration files require `load_snapshot NAME --force`, matching
the Just policy. Missing migration files and metadata errors block the
restore even with force. A failed SQL restore or migration leaves API and
Celery stopped so you can fix the error and retry. Restore error details
are saved privately in `.db-snapshots/.restore.log`. Commands in the same
worktree are locked against concurrent snapshot saves or loads.

## Worktree creation

`pilotcli env create-db-links -C .` is the database setup step for every
new web-platform worktree: the gtr hook (web-platform's local
`gtr.hook.postcreate`), CodeNexus's `.codenexus/scripts/postcreate.sh`
(which Orca's `.orca/scripts/setup.sh` runs), and `pilotcli env create`'s
own setup. It links `db.sql.gz` to the main checkout's production dump and
`.db-cache` to the shared development cache, then creates a private
`.db-snapshots/` directory. An existing checkpoint symlink is detached
without deleting shared files.

`.db-cache` is the shared `just dev` cache and `.db-snapshots` holds the
worktree's SQL checkpoints. Cache keys, cached files, and the
`just dev --report 0` cache-hit workflow are unchanged.
