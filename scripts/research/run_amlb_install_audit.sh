#!/usr/bin/env bash
# Host-side launcher for the AMLB install audit (paper-track claim A; see
# docs/research/paper-plan.md and amlb_install_audit_inner.sh next to this
# file). Run on a VPS as root, or (since 2026-10-21) on the local laptop as a
# docker-group user with OUT_DIR on the storage drive -- see
# docs/operations/local-storage.md. Ali OK'd the one part that still touches
# the laptop's system disk: Docker's own image/container layers under
# /var/lib/docker (base images plus the apt packages installed inside each
# container, removed by --rm).
#
# Everything heavy a container writes goes to a bind-mounted work dir under
# OUT_DIR instead of the container layer: the inner script's HOME (AMLB
# clone, its venvs, pip cache, AMLB user dir, OpenML cache) and TMPDIR (pip
# build dirs). Each image gets a fresh, empty work dir -- a clean room. A
# re-run refuses if the previous one's output is still there; FRESH=1 wipes
# it first.
#
# For each Ubuntu image (default: 22.04 = the OS AMLB's docs say they
# support, and 24.04 = the current LTS a new user is likely to have), starts
# a throwaway container (default 4 CPUs, 16GB RAM: the VPS shape; use
# MEMORY=8g on the 15GB laptop) and runs the inner audit script in it.
# Results land in $OUT_DIR/<image>/audit.csv (+ logs/, and home/ = the work
# dir). Note: inside a --memory-limited container AMLB still sizes jobs
# from the HOST's memory (psutil ignores the cgroup limit), so an exit 137
# (OOM kill) there may be the limit, not AMLB -- check before counting it.
#
# Docker here is purely a clean-room for measuring the ORIGINAL AMLB's
# documented install path; it is not part of CAML's own isolation model
# (CAML stays bare-metal uv venvs -- CLAUDE.md locked decision #2).
#
# Long-running (can take hours): launch detached, e.g.
#   setsid nohup bash run_amlb_install_audit.sh > amlb-audit.out 2>&1 < /dev/null & disown
#
# Env knobs: IMAGES, OUT_DIR, AMLB_REF (default stable), FRAMEWORKS,
# STEP_TIMEOUT (default 3600s per step), CPUS, MEMORY.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES="${IMAGES:-ubuntu:22.04 ubuntu:24.04}"
OUT_DIR="${OUT_DIR:-/root/amlb-audit}"
CPUS="${CPUS:-4}"
MEMORY="${MEMORY:-16g}"

if ! command -v docker >/dev/null; then
  echo "==> installing docker.io (apt)"
  apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io
fi

for image in $IMAGES; do
  tag="${image//[:\/]/-}"
  out="$OUT_DIR/$tag"
  if [[ -e "$out" ]]; then
    if [[ "${FRESH:-0}" == "1" && -n "$tag" ]]; then
      rm -rf -- "$out"
    else
      echo "==> $out already exists (a previous run); skipping $image. Re-run with FRESH=1 to redo it." >&2
      continue
    fi
  fi
  mkdir -p "$out/home"
  echo "==> $image -> $out"
  docker pull -q "$image"
  docker run --rm --cpus "$CPUS" --memory "$MEMORY" \
    -e AMLB_REF="${AMLB_REF:-stable}" \
    -e STEP_TIMEOUT="${STEP_TIMEOUT:-3600}" \
    -e HOME=/work -e TMPDIR=/work/tmp \
    -e AUDIT_LIMITS="cpus=$CPUS memory=$MEMORY" \
    ${FRAMEWORKS:+-e FRAMEWORKS="$FRAMEWORKS"} \
    -v "$out:/audit" \
    -v "$out/home:/work" \
    -v "$HERE/amlb_install_audit_inner.sh:/amlb_install_audit_inner.sh:ro" \
    "$image" bash /amlb_install_audit_inner.sh || echo "container for $image exited non-zero (see $out)"
done

echo "==> done. Summary:"
for image in $IMAGES; do
  tag="${image//[:\/]/-}"
  echo "--- $image"
  column -s, -t < "$OUT_DIR/$tag/audit.csv" 2>/dev/null || cat "$OUT_DIR/$tag/audit.csv"
done
