#!/usr/bin/env bash
# Push a code update to an ALREADY-provisioned CAML VPS (run from the
# operator's machine, inside this repo).
#
# Why this exists: scripts/setup_workspace.sh deliberately never overwrites
# an existing CAML/ checkout ("already present — leaving as-is"), so after
# the first provisioning, new code never reached the box by re-running
# provision_vps.sh -- sessions on 2026-09-10 and 2026-09-15 both fell back
# to scp-ing individual files by hand. This script makes that a one-liner.
#
# What it does:
#   1. packages HEAD (default) or the live working tree (INCLUDE_WORKTREE=1),
#      stamping a REVISION file (see scripts/lib_package.sh);
#   2. refuses to continue if a `caml run` / `caml sweep` is in progress on
#      the box (swapping code under a running sweep would silently mix
#      revisions between jobs) -- override with FORCE=1;
#   3. extracts it over ~caml/caml-workspace/CAML as the caml user. Only
#      source files are replaced: framework venvs, install markers, output/
#      and input/ are not in the archive, so installs and results survive.
#      (Files deleted locally are NOT deleted on the box -- harmless for
#      stale .py files nothing imports; re-provision from scratch if that
#      ever matters.)
#   4. runs `uv sync` (picks up orchestrator dependency changes), prints
#      the deployed revision, and refreshes /usr/local/bin/camlctl.
#
# Usage:
#   scripts/sync_vps.sh root@<host>
#   INCLUDE_WORKTREE=1 scripts/sync_vps.sh root@<host>
#   FORCE=1 scripts/sync_vps.sh root@<host>
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <user@host>   (user must have root/sudo; SSH must already work)" >&2
  exit 2
fi

SSH="${SSH:-ssh}"
SCP="${SCP:-scp}"
INCLUDE_WORKTREE="${INCLUDE_WORKTREE:-0}"
FORCE="${FORCE:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "must be run from inside the CAML git checkout." >&2; exit 1; }

if [[ -n "$(git status --porcelain)" && "$INCLUDE_WORKTREE" != "1" ]]; then
  echo "WARNING: working tree has uncommitted changes; syncing HEAD, not the working tree. Re-run with INCLUDE_WORKTREE=1 to sync the working tree instead." >&2
fi

if [[ "$FORCE" != "1" ]]; then
  # Bracket trick: '[c]aml' doesn't match this grep's own command line.
  running="$($SSH "$TARGET" "ps aux | grep -E '[c]aml (run|sweep)' || true")"
  if [[ -n "$running" ]]; then
    echo "Refusing to sync: a CAML job is running on $TARGET:" >&2
    echo "$running" >&2
    echo "Wait for it to finish (or stop it), or re-run with FORCE=1." >&2
    exit 1
  fi
fi

# A temp directory, not `mktemp --suffix` (GNU-only; it broke this script on macOS).
WORK_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/caml-sync.XXXXXX")"
ARCHIVE_LOCAL="$WORK_LOCAL/caml.tar.gz"
trap 'rm -rf "$WORK_LOCAL"' EXIT
source "$REPO_ROOT/scripts/lib_package.sh"
caml_package_archive "$ARCHIVE_LOCAL" "$INCLUDE_WORKTREE"
echo "==> packaged $([[ "$INCLUDE_WORKTREE" == 1 ]] && echo 'working tree' || echo 'HEAD') at $(git rev-parse --short HEAD)"

$SCP -q "$ARCHIVE_LOCAL" "$TARGET:/tmp/caml-sync.tar.gz"
$SSH "$TARGET" "chmod 0644 /tmp/caml-sync.tar.gz && \
  sudo -iu caml bash -lc 'cd ~/caml-workspace && tar xzf /tmp/caml-sync.tar.gz && cd CAML && uv sync -q && cat REVISION' && \
  rm -f /tmp/caml-sync.tar.gz && \
  if [ -f /home/caml/caml-workspace/CAML/scripts/camlctl ]; then install -m 0755 /home/caml/caml-workspace/CAML/scripts/camlctl /usr/local/bin/camlctl; fi"
echo "==> synced. Deployed revision shown above."
