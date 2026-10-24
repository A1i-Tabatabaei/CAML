#!/usr/bin/env bash
# Idempotent Ubuntu 24.04 system bootstrap for CAML. Safe to re-run.
# Run as root (or via sudo) — this is the *only* step in CAML's install
# flow that needs root; `caml install`/`caml run` should run as a
# dedicated non-root user created at the end of this script.
#
# Explicitly does NOT install: Python via apt, the `deadsnakes` PPA,
# Docker, or Singularity — see CLAUDE.md decisions #2/#3.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if [[ $EUID -ne 0 ]]; then
  echo "bootstrap_vps.sh must be run as root (or via sudo)." >&2
  exit 1
fi

echo "==> [1/6] apt baseline packages"
apt-get update -yq
apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
  build-essential curl ca-certificates git pkg-config \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
  openjdk-17-jre-headless \
  swig \
  unzip tmux htop

echo "==> [2/6] uv (Python interpreter + venv/package manager, no apt/PPA involved)"
CAML_USER="${CAML_USER:-caml}"
# A login shell as the caml user, without the XDG_* variables root's session
# may carry. GitHub's runners set XDG_CONFIG_HOME=/home/runner/.config
# system-wide; it reached the caml user through sudo and sent the uv
# installer's receipt to a directory caml can't write (CI's server-e2e,
# 2026-10-24). A server image with XDG variables in /etc/environment would
# do the same.
as_caml_login() {
  sudo -u "$CAML_USER" -H env -u XDG_CONFIG_HOME -u XDG_CACHE_HOME -u XDG_DATA_HOME -u XDG_STATE_HOME -u XDG_RUNTIME_DIR bash -lc "$1"
}
if ! id -u "$CAML_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$CAML_USER"
  echo "Created non-root user '$CAML_USER'. All 'caml install'/'caml run' work should run as this user."
fi

if ! as_caml_login 'command -v uv' >/dev/null 2>&1; then
  as_caml_login 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' /etc/profile.d/caml-uv-path.sh 2>/dev/null || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' > /etc/profile.d/caml-uv-path.sh
chmod 644 /etc/profile.d/caml-uv-path.sh

echo "==> [3/6] swapfile (safety net for H2O's JVM / AutoGluon / torch-based frameworks)"
total_mem_mb=$(free -m | awk '/^Mem:/{print $2}')
if [[ ! -f /swapfile ]] && [[ "$total_mem_mb" -lt 8192 ]]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -qxF '/swapfile none swap sw 0 0' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "Created 4G swapfile (system has ${total_mem_mb}MB RAM)."
else
  echo "Swapfile already present or system has >=8GB RAM; skipping."
fi

echo "==> [4/6] passwordless sudo for apt-get, scoped to the caml user (installer.py's _ensure_apt_packages uses 'sudo -n apt-get install')"
SUDOERS_FILE="/etc/sudoers.d/caml-apt"
if [[ ! -f "$SUDOERS_FILE" ]]; then
  echo "$CAML_USER ALL=(root) NOPASSWD: /usr/bin/apt-get install -y *" > "$SUDOERS_FILE"
  chmod 440 "$SUDOERS_FILE"
  visudo -c -f "$SUDOERS_FILE"
fi

echo "==> [5/6] camlctl, the one quote-free command operators run over SSH (ssh HOST camlctl help)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/camlctl" ]]; then
  install -m 0755 "$SCRIPT_DIR/camlctl" /usr/local/bin/camlctl
  echo "Installed /usr/local/bin/camlctl."
else
  echo "camlctl not found next to this script; skipping (provision_vps.sh and camlctl setup both ship it)."
fi

echo "==> [6/6] sanity report"
echo "--- versions ---"
as_caml_login 'uv --version' || true
java -version
gcc --version | head -1
echo "--- gpu (informational; CPU boxes are fully supported) ---"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
  echo "GPU present -> torch frameworks will install CUDA wheels by default (see docs/operations/gpu.md)."
else
  echo "no nvidia-smi -> CPU-only box; torch frameworks install CPU wheels. If this box HAS a GPU, install the NVIDIA driver first."
fi
echo "--- resources ---"
free -h
df -h /
echo "--- next step ---"
echo "Set up the workspace as $CAML_USER: scripts/setup_workspace.sh (camlctl setup and provision_vps.sh run it for you)."
