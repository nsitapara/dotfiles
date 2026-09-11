# Build from the main checkout's db.sql.gz in temporary, isolated Postgres.
prod_build() {
  python3 "$HOME/.config/herasight/db_snapshot.py" create "$@"
}

# Replace this checkout's database with the saved production baseline.
prod_seed() {
  python3 "$HOME/.config/herasight/db_snapshot.py" seed "$@"
}

# Remove this checkout's seeded database and restore plain Postgres.
prod_remove() {
  python3 "$HOME/.config/herasight/db_snapshot.py" remove "$@"
}

# SQL checkpoints are scoped to the current checkout directory.
save_snapshot() { python3 "$HOME/.config/herasight/db_snapshot.py" save-snapshot "$@"; }
load_snapshot() { python3 "$HOME/.config/herasight/db_snapshot.py" load-snapshot "$@"; }
list_snapshots() { python3 "$HOME/.config/herasight/db_snapshot.py" list-snapshots "$@"; }
list_snapshot() { list_snapshots "$@"; }
