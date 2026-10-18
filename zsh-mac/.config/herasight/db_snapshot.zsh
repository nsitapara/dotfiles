# The HeraSight database helpers, as zsh functions over pilotcli (pilotCLI milestone 11; they replace db_snapshot.py).
# Each passes -C "$PWD", so it acts on the checkout you are in, never $PILOT_WORKTREE_PATH's.
#   save_snapshot [name]     pilotcli env create-snapshot: a named SQL checkpoint of this checkout's database
#   list_snapshots           pilotcli env list-snapshots
#   load_snapshot [name] [--force]
#                            pilotcli env update-db --source snapshot: replace this checkout's database with a checkpoint
#                            (the latest when unnamed); --force accepts changed migration files
#   prod_build [--native|--docker]
#                            pilotcli env create-baseline: build the production baseline from the main checkout's
#                            db.sql.gz, on each available backend by default
#   prod_seed                pilotcli env update-db --source prod: load the production baseline into this checkout
#   prod_remove              pilotcli env update-db --source dev: remove it and restore development data
save_snapshot()  { pilotcli env create-snapshot -C "$PWD" "$@" --format text; }
list_snapshots() { pilotcli env list-snapshots -C "$PWD" --format text; }
list_snapshot()  { list_snapshots "$@"; }
load_snapshot()  { local -a a=(); local x; for x; do case $x in --force) a+=(--force true);; *) a+=(--snapshot "$x");; esac; done; pilotcli env update-db -C "$PWD" --source snapshot "${a[@]}" --format text; }
prod_build()     { local b=available; case ${1-} in --native) b=native;; --docker) b=docker;; esac; pilotcli env create-baseline --project web-platform --backend "$b" --format text; }
prod_seed()      { pilotcli env update-db -C "$PWD" --source prod --format text; }
prod_remove()    { pilotcli env update-db -C "$PWD" --source dev --format text; }
