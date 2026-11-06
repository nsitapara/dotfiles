# The HeraSight database helpers, as zsh functions over pilotcli (pilotCLI milestone 11; they replace db_snapshot.py).
# Each passes -C "$PWD", so it acts on the checkout you are in, never $PILOT_WORKTREE_PATH's.
#   snapshot_save [name]     pilotcli env create-snapshot: a named SQL checkpoint of this checkout's database
#   snapshot_list            pilotcli env list-snapshots
#   snapshot_load [name] [--force]
#                            pilotcli env update-db --source snapshot: replace this checkout's database with a checkpoint
#                            (the latest when unnamed); --force accepts changed migration files
#   prod_build [--native|--docker]
#                            pilotcli env create-baseline: build the production baseline from the main checkout's
#                            db.sql.gz, on each available backend by default
#   prod_seed                pilotcli env update-db --source prod: load the production baseline into this checkout
#   prod_remove              pilotcli env update-db --source dev: remove it and restore development data
snapshot_save()  { pilotcli env create-snapshot -C "$PWD" "$@" --format text; }
snapshot_list()  { pilotcli env list-snapshots -C "$PWD" --format text; }
snapshot_load()  { local -a a=(); local x; for x; do case $x in --force) a+=(--force true);; *) a+=(--snapshot "$x");; esac; done; pilotcli env update-db -C "$PWD" --source snapshot "${a[@]}" --format text; }
prod_build()     { local b=available; case ${1-} in --native) b=native;; --docker) b=docker;; esac; pilotcli env create-baseline --project web-platform --backend "$b" --format text; }
prod_seed()      { pilotcli env update-db -C "$PWD" --source prod --format text; }
prod_remove()    { pilotcli env update-db -C "$PWD" --source dev --format text; }

# clean_pg                 list every web-platform checkout's native Postgres size (prod = holds prod_seed data)
# clean_pg <name|path|.>   reset that checkout's Postgres: `just ndown` stops its stack and deletes .local/native;
#                          the next `just dev` restores development data from the shared cache
# clean_pg --prod          reset every checkout that holds prod_seed data
# clean_pg --all           reset every checkout's Postgres
# clean_pg --stopped       reset every checkout whose native stack isn't running
clean_pg() {
  local main=/Users/nishsitapara/Documents/web-platform wt d size flags pid
  local -a all=() targets=()
  all=(${(f)"$(git -C $main worktree list --porcelain | sed -n 's/^worktree //p')"})
  _clean_pg_row() {
    d=$1/.local/native; size=$(du -sh $d 2>/dev/null | cut -f1); flags=""
    [[ -e $d/prod-seed ]] && flags+=" prod"
    for pid in $d/run/*.pid(N); do kill -0 $(<$pid) 2>/dev/null && { flags+=" running"; break; }; done
    printf '%6s %-13s %s\n' $size "${flags# }" ${1:t}
  }
  case ${1-} in
    "")
      for wt in $all; do [[ -d $wt/.local/native ]] && _clean_pg_row $wt; done | sort -h
      df -h /System/Volumes/Data | awk 'NR==2 { print "\nfree: " $4 " (" $5 " used)" }'
      return ;;
    --all)  for wt in $all; do [[ -d $wt/.local/native ]] && targets+=$wt; done ;;
    --prod) for wt in $all; do [[ -e $wt/.local/native/prod-seed ]] && targets+=$wt; done ;;
    --stopped)
      for wt in $all; do
        [[ -d $wt/.local/native ]] || continue
        local live=0
        for pid in $wt/.local/native/run/*.pid(N); do kill -0 $(<$pid) 2>/dev/null && { live=1; break; }; done
        (( live )) || targets+=$wt
      done ;;
    *)
      if [[ -d $1 ]]; then wt=${1:A}
      else wt=${${(M)all:#*/$1}[1]}; fi
      [[ -n $wt && -d $wt/.local/native ]] || { echo "clean_pg: no native data for '$1'" >&2; return 1; }
      targets=($wt) ;;
  esac
  (( ${#targets} )) || { echo "clean_pg: nothing to reset"; return 0; }
  echo "Reset Postgres (stop the stack, delete .local/native) in:"
  for wt in $targets; do _clean_pg_row $wt; done
  read -q "?Continue? [y/N] " || { echo; return 1; }
  echo
  for wt in $targets; do
    [[ -f $wt/justfile.native ]] || { echo "skip ${wt:t}: no justfile.native (Docker-only checkout)"; continue; }
    (cd $wt && just ndown)
  done
  df -h /System/Volumes/Data | awk 'NR==2 { print "free: " $4 " (" $5 " used)" }'
}
