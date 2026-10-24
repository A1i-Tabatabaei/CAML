#!/usr/bin/env bash
# Run a long CAML command (an install, a sweep) from the local storage
# workspace that scripts/sync_local.sh set up: detached from the terminal (it
# survives the terminal or the Claude session closing), with system sleep,
# idle suspend and lid-close suspend blocked for as long as it runs, and its
# output going to $CAML_STORAGE/logs/<name>.log.
#
# Usage:
#   CAML_STORAGE=/mnt/MIRC/CAML-STORAGE scripts/run_local_detached.sh <name> <command...>
# e.g.
#   ... scripts/run_local_detached.sh install-flaml caml install FLAML
#   ... scripts/run_local_detached.sh pilot caml sweep FLAML GAMA --benchmark pilot --constraint pilot
#
# Check on it:   tail -f $CAML_STORAGE/logs/<name>.log
# Stop it:       kill -TERM -- -$(cat $CAML_STORAGE/logs/<name>.pid)   (the whole process group)
set -euo pipefail

STORAGE="${CAML_STORAGE:-}"
if [[ -z "$STORAGE" || $# -lt 2 ]]; then
  echo "usage: CAML_STORAGE=<dir> $0 <name> <command...>" >&2
  exit 2
fi
[[ -f "$STORAGE/caml-env.sh" ]] || { echo "$STORAGE/caml-env.sh missing: run scripts/sync_local.sh first." >&2; exit 1; }

name="$1"; shift
log="$STORAGE/logs/$name.log"
pidfile="$STORAGE/logs/$name.pid"
mkdir -p "$STORAGE/logs"
if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
  echo "'$name' is already running (pid $(cat "$pidfile")); log: $log" >&2
  exit 1
fi

# setsid: new session and process group, so the pid file's pid is also the
# group id that kill -TERM -- -<pid> takes.
setsid nohup systemd-inhibit --what=sleep:idle:handle-lid-switch --who=CAML \
  --why="CAML: $name" --mode=block \
  bash -c 'source "$0/caml-env.sh" && cd "$CAML_ROOT" && echo "== $(date -u +%FT%TZ) start: $*" && "$@"; rc=$?; echo "== $(date -u +%FT%TZ) exit $rc"; exit $rc' \
  "$STORAGE" "$@" >"$log" 2>&1 </dev/null &
echo $! >"$pidfile"
disown
echo "started '$name' (pid $(cat "$pidfile")); log: $log"
