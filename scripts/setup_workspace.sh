#!/usr/bin/env bash
# Idempotent CAML workspace setup. Run as the non-root `caml` user AFTER
# scripts/bootstrap_vps.sh has run as root. Safe to re-run.
#
# Reproduces the sibling workspace layout (see CLAUDE.md) and gets the
# orchestrator ready to install/run frameworks:
#
#   $WORKSPACE_DIR/
#   ├── CAML/                      # this repo
#   └── automlbenchmark-reference/ # read-only public AMLB clone (attribution/diff only)
#
# then `uv sync` + `uv run caml doctor`.
#
# The CAML repo is private. Rather than requiring GitHub credentials on the
# VPS, the default delivery mechanism is a git-archive tarball pushed up by
# the operator (see scripts/provision_vps.sh) — no secret ever lands on the
# box. Set CAML_SRC to that tarball. If instead you have repo credentials on
# the box (deploy key / token in the git URL), point CAML_SRC at a git URL.
#
# Env knobs (all optional):
#   WORKSPACE_DIR  workspace root                (default: $HOME/caml-workspace)
#   CAML_SRC       path to a *.tar.gz git-archive (prefix CAML/) on this box,
#                  OR a git URL to clone          (default: $CAML_REPO_URL)
#   CAML_REPO_URL  git URL used when CAML_SRC is unset
#                                                 (default: the public-clone-friendly HTTPS URL below)
#   CAML_REF       branch, tag or commit to check out after a git clone
#                                                 (default: the repo's default branch)
#   AMLB_REF_URL   AMLB reference clone URL       (default: openml/automlbenchmark)
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-$HOME/caml-workspace}"
CAML_REPO_URL="${CAML_REPO_URL:-https://github.com/A1i-Tabatabaei/CAML.git}"
CAML_SRC="${CAML_SRC:-$CAML_REPO_URL}"
AMLB_REF_URL="${AMLB_REF_URL:-https://github.com/openml/automlbenchmark.git}"

if [[ $EUID -eq 0 ]]; then
  echo "setup_workspace.sh should run as the non-root 'caml' user, not root." >&2
  echo "Try:  sudo -iu caml bash $(readlink -f "$0")" >&2
  exit 1
fi

# Make uv visible even in a non-login shell (bootstrap installs it to ~/.local/bin).
if [[ -f "$HOME/.local/bin/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.local/bin/env"
else
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { echo "uv not found on PATH — run scripts/bootstrap_vps.sh as root first." >&2; exit 1; }

echo "==> [1/4] workspace dir: $WORKSPACE_DIR"
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

echo "==> [2/4] CAML repo"
if [[ -d CAML/.git || -f CAML/pyproject.toml ]]; then
  echo "    CAML/ already present — leaving as-is (delete it to force a re-fetch)."
elif [[ -f "$CAML_SRC" ]]; then
  echo "    extracting archive: $CAML_SRC"
  tar xzf "$CAML_SRC"
  [[ -d CAML ]] || { echo "archive did not contain a CAML/ directory (create it with 'git archive --prefix=CAML/')." >&2; exit 1; }
else
  echo "    cloning: $CAML_SRC"
  git clone "$CAML_SRC" CAML
  if [[ -n "${CAML_REF:-}" ]]; then
    echo "    checking out: $CAML_REF"
    git -C CAML checkout -q "$CAML_REF"
  fi
fi

echo "==> [3/4] AMLB reference clone (read-only, attribution/diff only)"
if [[ -d automlbenchmark-reference/.git ]]; then
  echo "    automlbenchmark-reference/ already present — leaving as-is."
else
  git clone --depth 1 "$AMLB_REF_URL" automlbenchmark-reference
fi

echo "==> [4/4] uv sync + caml doctor"
cd CAML
uv sync
uv run caml doctor

echo
echo "Workspace ready at $WORKSPACE_DIR/CAML."
echo "Next (from your machine): ssh <host> camlctl install FLAML, then ssh <host> camlctl caml run FLAML --benchmark test --constraint test"
