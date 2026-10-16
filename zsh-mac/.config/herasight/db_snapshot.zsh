# Build the production baseline from the main checkout's db.sql.gz in an isolated
# Postgres: a native cluster and/or a Docker image. --native or --docker builds one;
# by default it builds each backend that is available.
prod_build() {
  python3 "$HOME/.config/herasight/db_snapshot.py" create "$@"
}

# Replace this checkout's database with the saved production baseline, on the
# backend the checkout runs (native stack or Docker).
prod_seed() {
  python3 "$HOME/.config/herasight/db_snapshot.py" seed "$@"
}

# Remove this checkout's production data and restore development data.
prod_remove() {
  python3 "$HOME/.config/herasight/db_snapshot.py" remove "$@"
}

# SQL checkpoints are scoped to the current checkout directory, on either backend.
# They refuse to save while production data from prod_seed is loaded.
save_snapshot() { python3 "$HOME/.config/herasight/db_snapshot.py" save-snapshot "$@"; }
load_snapshot() { python3 "$HOME/.config/herasight/db_snapshot.py" load-snapshot "$@"; }
list_snapshots() { python3 "$HOME/.config/herasight/db_snapshot.py" list-snapshots "$@"; }
list_snapshot() { list_snapshots "$@"; }
