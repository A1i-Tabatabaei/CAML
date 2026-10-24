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

echo "==> [1/5] apt baseline packages"
apt-get update -yq
apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
  build-essential curl ca-certificates git pkg-config \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
  openjdk-17-jre-headless \
  swig \
  unzip tmux htop

echo "==> [2/5] uv (Python interpreter + venv/package manager, no apt/PPA involved)"
CAML_USER="${CAML_USER:-caml}"
if ! id -u "$CAML_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$CAML_USER"
  echo "Created non-root user '$CAML_USER'. All 'caml install'/'caml run' work should run as this user."
fi
CAML_HOME=$(getent passwd "$CAML_USER" | cut -d: -f6)

if ! sudo -u "$CAML_USER" bash -lc 'command -v uv' >/dev/null 2>&1; then
  sudo -u "$CAML_USER" bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' /etc/profile.d/caml-uv-path.sh 2>/dev/null || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' > /etc/profile.d/caml-uv-path.sh
chmod 644 /etc/profile.d/caml-uv-path.sh

echo "==> [3/5] swapfile (safety net for H2O's JVM / AutoGluon / torch-based frameworks)"
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

echo "==> [4/5] passwordless sudo for apt-get, scoped to the caml user (installer.py's _ensure_apt_packages uses 'sudo -n apt-get install')"
SUDOERS_FILE="/etc/sudoers.d/caml-apt"
if [[ ! -f "$SUDOERS_FILE" ]]; then
  echo "$CAML_USER ALL=(root) NOPASSWD: /usr/bin/apt-get install -y *" > "$SUDOERS_FILE"
  chmod 440 "$SUDOERS_FILE"
  visudo -c -f "$SUDOERS_FILE"
fi

echo "==> [5/5] sanity report"
echo "--- versions ---"
sudo -u "$CAML_USER" bash -lc 'uv --version' || true
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
echo "--- next steps ---"
echo "1. su - $CAML_USER"
echo "2. clone the CAML repo and the automlbenchmark-reference repo as siblings under ~$CAML_USER/ (see CLAUDE.md workspace layout)"
echo "3. cd CAML && uv sync"
echo "4. uv run caml doctor"
