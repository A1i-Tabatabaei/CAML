#!/usr/bin/env bash
# Operator-side: deletes the CAML workspace on a target VPS -- the repo
# checkout, the read-only AMLB reference clone, every framework's venv,
# and all benchmark run outputs. Run this before scripts/provision_vps.sh
# when the goal is a genuinely clean redeploy (not an incremental sync),
# e.g. to verify the documented provisioning process alone reproduces a
# working system with no leftover state masking a gap in the docs.
#
# Deliberately does NOT touch:
#   - the `caml` OS user, its home directory outside caml-workspace/, or
#     anything in its shell profile (e.g. TABPFN_TOKEN, see
#     docs/operations/tabpfn-access.md) -- that's a credential, not
#     project state, and nothing in this repo's docs describes tearing
#     it down as part of a redeploy.
#   - apt packages / sudoers / swap installed by bootstrap_vps.sh --
#     that script is documented as idempotent and safe to re-run, so
#     there's no need to destroy and recreate the OS-level baseline
#     first; scripts/provision_vps.sh's next run reconciles it.
#
# Usage:
#   scripts/teardown_workspace.sh <user@host>
#
# Assumes working SSH to the target (key-based auth or an ~/.ssh/config
# entry, same assumption as provision_vps.sh). Override the transport
# command for non-standard auth:
#   SSH="ssh -F my_ssh_config" scripts/teardown_workspace.sh caml-vps
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <user@host>   (user must have root/sudo, or be able to sudo -iu caml; SSH must already work)" >&2
  exit 2
fi

SSH="${SSH:-ssh}"

echo "==> Tearing down CAML workspace on $TARGET"
# Piped over stdin (`bash -s`) rather than inlined as a quoted string --
# avoids escaping $HOME across three nested shells (local -> ssh's remote
# login shell -> sudo's caml shell). The quoted heredoc delimiter
# ('REMOTE_SCRIPT') stops *local* bash from touching anything inside it;
# it arrives at the remote `bash -s` completely literally.
$SSH "$TARGET" "sudo -iu caml bash -s" <<'REMOTE_SCRIPT'
if [ -d "$HOME/caml-workspace" ]; then
  du -sh "$HOME/caml-workspace" 2>/dev/null || true
  rm -rf "$HOME/caml-workspace"
  echo "caml-workspace removed."
else
  echo "caml-workspace did not exist -- nothing to remove."
fi
REMOTE_SCRIPT

echo "==> Done. Re-provision with: scripts/provision_vps.sh $TARGET"
