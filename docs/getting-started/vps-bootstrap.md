# VPS bootstrap

Target: a fresh Ubuntu 24.04 LTS server (CPU-only for now; GPU support is
backlog, see `STATUS.md` Phase 8), with root/sudo SSH access.

## Fastest path: one-shot provisioning

From a checkout of this repo on your own machine (with working SSH to the
box — key-based auth or an `~/.ssh/config` entry):

```bash
scripts/provision_vps.sh root@<vps>
```

That single command does the whole Phase-2 flow end to end and is
idempotent (safe to re-run):

1. **Packages HEAD** with `git archive` (tracked files only — no local
   venvs, no gitignored secrets) and pushes it to the box. This is how the
   **private** CAML repo reaches the VPS without any GitHub credential ever
   landing there — see "Why an archive, not `git clone`" below.
2. Runs `scripts/bootstrap_vps.sh` as **root** (the only step needing root).
3. Runs `scripts/setup_workspace.sh` as the **caml** user: reproduces the
   workspace layout, `uv sync`, `uv run caml doctor`.

When it finishes the box is ready for `uv run caml install <framework>`.
For non-key-based auth or a custom SSH config, override the transport
commands, e.g. `SSH="ssh -F my_config" SCP="scp -F my_config"
scripts/provision_vps.sh caml-vps`.

Verified end to end on a real Ubuntu 24.04 VPS on 2026-07-21 (Phase 2):
fresh box → both reference frameworks (FLAML, MLJAR-supervised) installed
and smoke-tested with real non-NaN scores.

## What the two scripts do, step by step

If you'd rather run the halves yourself (or need to understand what the
one-shot did), it's exactly these two scripts.

### 1. `scripts/bootstrap_vps.sh` — run as root

```bash
scp scripts/bootstrap_vps.sh root@<vps>:/root/
ssh root@<vps> 'bash /root/bootstrap_vps.sh'
```

This is the **only** step that needs root. It:

1. Installs apt baseline packages (build toolchain, `openjdk-17-jre-headless`
   for H2O, `swig` for MLJAR-supervised, no `deadsnakes` PPA anywhere).
2. Creates a dedicated non-root `caml` user and installs `uv` for that user.
3. Adds a 4G swapfile if the box has <8GB RAM (H2O's JVM, AutoGluon, and
   torch-based frameworks are memory-hungry).
4. Grants the `caml` user passwordless `sudo apt-get install` only (scoped,
   not full root) — `installer.py`'s `_ensure_apt_packages` needs this for
   any framework-declared system packages not already covered by bootstrap.

See `scripts/bootstrap_vps.sh` for the exact commands; it's short and
meant to be read, not just trusted.

### 2. `scripts/setup_workspace.sh` — run as the caml user

```bash
sudo -iu caml bash setup_workspace.sh          # or: su - caml; bash setup_workspace.sh
```

Idempotent. Reproduces the sibling workspace layout, then `uv sync` +
`uv run caml doctor`:

```
~caml/caml-workspace/
├── CAML/                          # this repo
└── automlbenchmark-reference/     # read-only public AMLB clone (attribution/diff only)
```

`provision_vps.sh` delivers the CAML repo from the archive it pushed
(`CAML_SRC=/tmp/caml.tar.gz`). Run on its own, `setup_workspace.sh` clones
the public repo (`CAML_REPO_URL`, default
`https://github.com/A1i-Tabatabaei/CAML.git`). Set `CAML_SRC` to any git URL
or archive to override. See the script header for all env knobs
(`WORKSPACE_DIR`, `CAML_SRC`, `CAML_REPO_URL`, `AMLB_REF_URL`).

See `CLAUDE.md`'s workspace-layout section for why the reference clone is
kept as a sibling, never nested inside CAML.

## Why an archive, not `git clone`

`provision_vps.sh` pushes a `git archive` of your committed HEAD over the
same SSH connection you already have, so the server runs exactly the code in
your clone, including local commits and forks that were never pushed, and
needs no GitHub access at all. Since v1.0.0 the repo is public, so a plain
`git clone https://github.com/A1i-Tabatabaei/CAML.git` on the box also
works (the manual route in the README).

History: the archive route was added in 2026-07, when the repo was still
private and a fresh VPS had no credentials to clone it. It avoided shipping
a deploy key or token (a standing secret to manage and rotate) to every
server.

Two follow-ons (2026-10-21):

- **Provenance**: the archive carries a `REVISION` file (`commit=`,
  `branch=`, `dirty=`), written by `scripts/lib_package.sh`. With no `.git`
  on the box, CAML reads it so that `results.csv`'s `app_version` records the
  exact commit instead of `dev [NA, NA]`.
- **Updating an existing box**: `setup_workspace.sh` never overwrites an
  existing `CAML/`, so re-running `provision_vps.sh` does **not** deploy new
  code. Use `scripts/sync_vps.sh root@<host>` instead, with
  `INCLUDE_WORKTREE=1` for uncommitted work. It refuses while a `caml
  run`/`caml sweep` is active (`FORCE=1` overrides), replaces only source
  files (venvs, `output/` and `input/` survive), and runs `uv sync`.

## Recommended VPS sizing

**≥50GB disk, ≥8GB RAM (16GB+ preferred).** 11 isolated venvs with largely
non-shared heavy dependencies (torch, lightgbm, xgboost, catboost, sklearn
duplicated per-venv by design) plus H2O/AutoGluon/LightAutoML's RAM
appetite can plausibly reach 15–30GB+ of disk. `caml doctor` warns if free
disk is under 50GB. (For reference, the Phase-2 box was 4 vCPU / 7.8GB RAM
/ 232GB disk; the two reference frameworks' venvs alone use ~2.2GB.)

## Start installing frameworks

See `operations/vps-runbook.md` for the per-framework install → smoke-test
→ fix → verify loop.
