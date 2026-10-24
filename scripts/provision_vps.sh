#!/usr/bin/env bash
# One-shot CAML provisioning for a fresh Ubuntu 24.04 VPS, run from the
# operator's machine (inside a checkout of this repo). Does the whole
# Phase-2 flow end to end:
#
#   1. package the source (HEAD by default, or the live working tree — see
#      INCLUDE_WORKTREE below) and push it + the setup scripts to the box.
#   2. run scripts/bootstrap_vps.sh as root (apt baseline, uv, caml user,
#      swap, scoped sudo).
#   3. run scripts/setup_workspace.sh as the caml user, feeding it the
#      pushed archive (so the private CAML repo never needs credentials on
#      the VPS) — reproduces the workspace, uv sync, caml doctor.
#
# Idempotent: safe to re-run. After it finishes the box is ready for
# `uv run caml install <framework>`.
#
# Usage:
#   scripts/provision_vps.sh root@<host>
#   INCLUDE_WORKTREE=1 scripts/provision_vps.sh root@<host>
#
# INCLUDE_WORKTREE=1 packages the live working tree (tracked + untracked,
# gitignored-excluded — same rule `git status` uses) instead of `HEAD`, for
# verifying not-yet-committed changes on a real VPS before deciding whether
# to commit. Added 2026-09-15 after two separate sessions (2026-09-10,
# 2026-09-15) each needed a hand-rolled `git ls-files -co --exclude-standard
# | tar czf ...` workaround for exactly this — `git archive HEAD` only ever
# sees the last commit, never uncommitted work.
#
# Assumes working SSH to the target (key-based auth or an ~/.ssh/config
# entry — the committed script deliberately handles no passwords). For
# non-standard access, override the transport commands, e.g.:
#   SSH="ssh -F my_ssh_config" SCP="scp -F my_ssh_config" \
#     scripts/provision_vps.sh caml-vps
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <user@host>   (user must have root/sudo; SSH must already work)" >&2
  exit 2
fi

# Transport commands — overridable for non-key-based auth / custom configs.
SSH="${SSH:-ssh}"
SCP="${SCP:-scp}"
INCLUDE_WORKTREE="${INCLUDE_WORKTREE:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "must be run from inside the CAML git checkout." >&2; exit 1; }

if [[ -n "$(git status --porcelain)" && "$INCLUDE_WORKTREE" != "1" ]]; then
  echo "WARNING: working tree has uncommitted changes; provisioning HEAD (committed state), not the working tree. Re-run with INCLUDE_WORKTREE=1 to package the working tree instead." >&2
fi

REMOTE_TMP="/tmp/caml-provision"
# A temp directory, not `mktemp --suffix` (GNU-only; it broke this script on macOS).
WORK_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/caml-provision.XXXXXX")"
ARCHIVE_LOCAL="$WORK_LOCAL/caml.tar.gz"
trap 'rm -rf "$WORK_LOCAL"' EXIT

if [[ "$INCLUDE_WORKTREE" == "1" ]]; then
  echo "==> [1/3] packaging the live working tree (tracked + untracked, gitignore-excluded) and pushing to $TARGET"
else
  echo "==> [1/3] packaging HEAD ($(git rev-parse --short HEAD)) and pushing to $TARGET"
fi
# Shared with scripts/sync_vps.sh: builds the archive and stamps a REVISION
# file into it (the box has no .git, so this is how results.csv's
# app_version stays traceable to an exact commit).
source "$REPO_ROOT/scripts/lib_package.sh"
caml_package_archive "$ARCHIVE_LOCAL" "$INCLUDE_WORKTREE"
$SSH "$TARGET" "mkdir -p $REMOTE_TMP"
$SCP -q "$ARCHIVE_LOCAL"            "$TARGET:$REMOTE_TMP/caml.tar.gz"
$SCP -q scripts/bootstrap_vps.sh   "$TARGET:$REMOTE_TMP/bootstrap_vps.sh"
$SCP -q scripts/setup_workspace.sh "$TARGET:$REMOTE_TMP/setup_workspace.sh"

echo "==> [2/3] running bootstrap_vps.sh as root"
$SSH "$TARGET" "bash $REMOTE_TMP/bootstrap_vps.sh"

echo "==> [3/3] running setup_workspace.sh as the caml user (repo delivered via pushed archive)"
# Stage the archive + script where the caml user can read them, then run as caml.
$SSH "$TARGET" "install -m 0644 $REMOTE_TMP/caml.tar.gz /tmp/caml.tar.gz && \
                install -m 0755 $REMOTE_TMP/setup_workspace.sh /tmp/setup_workspace.sh && \
                sudo -iu caml env CAML_SRC=/tmp/caml.tar.gz bash /tmp/setup_workspace.sh"

echo
echo "Provisioning complete. The box is ready. To install + smoke-test a framework:"
echo "  $SSH $TARGET \"sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml install flaml && uv run caml run flaml --benchmark test --constraint test'\""
