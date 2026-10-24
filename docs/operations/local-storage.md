# Running CAML locally from a storage drive

> **Status: abandoned on 2026-10-21, the same day, because of the network.**
> Ali: "forget about local as my network is trash. i'll provide the vps".
> FLAML installed fine (32 min at about 2 MB/s through Ali's proxy). Its
> smoke test then hung on the very first OpenML request. openml.org was
> unreachable from the laptop's network: a direct TCP connect "succeeded"
> in 9 ms (impossible to the Netherlands, so it was locally intercepted)
> and the TLS handshake was never answered. Through the proxy, the
> `CONNECT` was never answered either. openml.org also failed from an
> outside vantage point (Claude's WebFetch) at the same time, while PyPI
> worked, so OpenML itself may have been down too (KI-07). The run was
> stopped, and at Ali's request everything on the drive and the old
> system-disk leftovers were deleted. **The scripts and the
> `STORAGE_ENV_VARS` fix stay**, for any machine with a usable network.
> Everything below describes the setup as built and checked.

Since 2026-10-21 the paper-track runs (pilot first) happen on Ali's own
laptop instead of a rented VPS, to save money. The laptop's system disk
had about 13GB free, so **everything CAML installs or writes lives on an
external drive** at `/mnt/MIRC/CAML-STORAGE`. That includes framework
venvs, uv's cache, the Python interpreters, OpenML datasets, results, temp
files and every tool's `~/.cache`. Nothing new goes on the system disk.

This page covers the setup, how the redirection works, how it was checked,
and the caveats of a shared laptop as a benchmark box.

## The machine (probed 2026-10-21)

| Part | Value |
|---|---|
| CPU | Intel i7-11370H, 4 cores / 8 threads (laptop H-series) |
| RAM | 15GB total; about 5GB available with Ali's normal desktop session open; 4GB swap |
| GPU | NVIDIA GeForce RTX 3060 Laptop, 6GB, driver 580.159.03 |
| OS | Ubuntu 24.04.4 LTS |
| System disk | 215GB NVMe, about 13–15GB free. **Must not grow.** |
| Storage drive | Toshiba MQ04ABF100 1TB 2.5" USB HDD (spinning), NTFS mounted through ntfs-3g (`fuseblk`, `rw,allow_other`), 666GB free |
| System packages CAML needs | `build-essential`, `swig`, `openjdk-17-jre-headless` already installed, so `caml install`'s `dpkg -s` check passes and never calls `sudo apt-get` |

### Does NTFS-over-FUSE work for Python venvs?

Yes. Probed before anything was installed, with a scratch directory on the
drive:

| Feature | Result |
|---|---|
| symlinks (`uv venv`'s `bin/python`) | ok |
| hardlinks (uv's cache → venv linking) | ok |
| atomic rename-over | ok |
| FIFOs, Unix sockets (multiprocessing, Ray) | ok |
| `flock` + `lockf` (`caml sweep`'s lock) | ok |
| shared `mmap` | ok |
| executing scripts | ok (mounted without `noexec`; ntfs-3g reports every file as mode 777) |
| case sensitivity, `:` in names | ok |
| sequential write | ~94 MB/s |

It's slow, though. A cold `uv sync` of the orchestrator took 6.5 minutes, and
framework installs and cold Python imports are slower than on a VPS SSD.
That costs wall-clock time but not correctness.

## Layout and commands

```
/mnt/MIRC/CAML-STORAGE/
  caml-env.sh        source before any caml command (regenerated on every sync)
  secrets.env        optional, Ali's own: export TABPFN_TOKEN=...  (never committed)
  workspace/CAML/    deployed code + frameworks/*/venv, .venv, output/
  home/              HOME for caml and every framework subprocess
  cache/ config/ data/ state/   XDG_* dirs (uv cache, openml, HF/torch weights, ...)
  python/            uv-managed Python interpreters
  tmp/               TMPDIR
  logs/              detached-run logs and pid files
```

Deploy or update the code from the repo (the first run creates the
layout). The workspace is a **deployed copy**, the same model as a VPS:
edit code in the repo, then re-sync.

```bash
INCLUDE_WORKTREE=1 CAML_STORAGE=/mnt/MIRC/CAML-STORAGE scripts/sync_local.sh
```

Use any CAML command interactively:

```bash
source /mnt/MIRC/CAML-STORAGE/caml-env.sh && caml status
```

Run a long command (an install or a sweep) detached, with sleep blocked:

```bash
CAML_STORAGE=/mnt/MIRC/CAML-STORAGE scripts/run_local_detached.sh pilot caml sweep FLAML GAMA --benchmark pilot --constraint pilot
```

The log goes to `logs/<name>.log`. Stop the run with
`kill -TERM -- -$(cat logs/<name>.pid)`, which stops the whole process group.

`sync_local.sh` refuses to run while a `caml run|sweep|install` from the
workspace is in progress (`FORCE=1` overrides). It also refuses if
`CAML_STORAGE` is on the same filesystem as `/` (`ALLOW_SYSTEM_DISK=1`
overrides). Like `sync_vps.sh`, it doesn't delete workspace files that
were deleted in the repo (KI-06).

`run_local_detached.sh` wraps the command in `setsid nohup systemd-inhibit
--what=sleep:idle:handle-lid-switch`. The run survives the terminal or
Claude session closing, and the laptop won't suspend (closing the lid
included) until it finishes. Keep it on AC power. No sudo is needed;
polkit allows this for the active desktop user.

## How the redirection works

`caml-env.sh` sets:

| Variable | Points to | Catches |
|---|---|---|
| `HOME` | `home/` | anything that writes under `~` without honoring XDG |
| `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` | `cache/` … | openml datasets, HF hub/TabPFN weights, torch hub, matplotlib, ... |
| `UV_CACHE_DIR` | `cache/uv` | every downloaded wheel (shared by all venvs via hardlinks) |
| `UV_PYTHON_INSTALL_DIR`, `UV_PYTHON_BIN_DIR` | `python/` | `uv python install` interpreters and their `python3.X` shims. Without `UV_PYTHON_BIN_DIR`, uv would also drop shims into `~/.local/bin` and could clash with Ali's own. |
| `UV_PYTHON_PREFERENCE=only-managed` | | Venvs only use interpreters under `python/`. Without it, the first sync built the orchestrator `.venv` on a uv Python that already lived on the system disk (`~/.local/share/uv/python`). Nothing new was written there, but the drive wasn't self-contained. |
| `TMPDIR`, `TMP`, `TEMP` | `tmp/` | dataset hand-off files, Ray's session dir, H2O's `ice_root` (h2o-py makes it with `tempfile.mkdtemp()`, still to confirm on a live run: KI-14) |
| `CAML_ROOT`, `PATH` | `workspace/CAML` | `caml` resolves to the workspace's own `.venv` from any directory |

**One code change was needed** (`frameworks/shared/caller.py`,
`retained_env()` / `STORAGE_ENV_VARS`). `run_cmd` *replaces* a framework
subprocess's whole environment, and `run_in_venv` passed through only
`TMP/TEMP/TMPDIR` plus a per-framework list. A redirected `HOME` or
`XDG_CACHE_HOME` would therefore never have reached 7 of the 10
frameworks. Python's `expanduser()` then falls back to the passwd entry
(the real home directory), so their caches would have silently landed on the
system disk. `HOME` and the four `XDG_*` variables now always cross when
set. That's behavior-neutral on a normal box, where they equal the real
home anyway. Unit-tested in `tests/test_caller_ipc.py`.

`caml doctor`'s disk check used to measure `/`. It now measures the
filesystem holding the workspace, and prints which one.

## Checks done

- Before and after deploying plus building the orchestrator venv, system-disk
  free space went 15496MB → 15632MB, i.e. unchanged (it went *up* from
  unrelated desktop activity). It gets re-checked after each framework
  install; the install script prints `df` for both disks.
- `caml doctor` on the workspace reports 665.5GB free on the drive. All
  three apt packages are present, and the GPU is detected.

## Caveats of a laptop as a benchmark box

- **RAM is the binding limit.** About 5GB is free with the desktop session
  open. When a constraint sets no `max_mem_size_mb`, CAML (like AMLB)
  gives each job whatever memory is free at that moment, so the budget
  varies from job to job with Ali's other apps. That's fine for the pilot,
  which is about finding bugs. For paper-grade numbers: close heavy apps,
  set a fixed `max_mem_size_mb`, and report the hardware. Run one job at
  a time (`caml sweep` already does).
- **Measurement noise.** A shared desktop with thermal throttling is a
  noisier timing environment than a dedicated VPS (KI-33).
- **The GPU is present, so CAML's auto-detection would install CUDA wheels**
  for TabPFN, AutoGluon and LightAutoML. The pilot installs with
  `CAML_COMPUTE=cpu` instead. That matches AMLB's CPU-only protocol and the
  configuration verified on every VPS, and it keeps the comparison fair
  across frameworks. The RTX 3060 is a chance to finally verify KI-10/KI-11
  (the GPU fixes left unverified since 2026-08-02), as a separate step that
  reinstalls those three frameworks with GPU wheels.
- **The drive must stay mounted.** Unplugging it kills the run. `caml sweep`
  resumes from its ledger when re-run.
- **Docker is the one exception (approved by Ali, 2026-10-21).** The AMLB
  install audit (`scripts/research/`) runs in Docker, whose data root is
  `/var/lib/docker` on the system disk. The launcher bind-mounts each
  container's HOME and TMPDIR onto the drive (`$OUT_DIR/<image>/home`),
  so the AMLB clone, venvs, pip cache and build dirs stay off the system
  disk. Only the base images and the apt packages installed inside a
  container land there, and `--rm` removes the latter. A container
  writing symlinks/FIFOs into the NTFS bind mount was tested OK.
- **Fallback rule (Ali, 2026-10-21)**: keep everything on the drive. If
  something genuinely can't live there, the system disk may be used (Ali
  freed space for this: it went from about 15GB to 65GB free). Record each
  such case here.
- **Provenance**: a dirty working tree is stamped `dirty=1` against the last
  commit. Commit before paper-grade runs so `app_version` pins an exact
  revision.

## Pre-existing items on the system disk (not created by this setup)

These were from July 2026, before the "no local installs" rule. **The first
three were deleted on 2026-10-21 with Ali's OK.** The system disk gained
about 2GB net, since part of the uv cache was hardlinked into envs that
still use it. Ali's uv tools were checked afterwards and still work.

| Path | Size | What |
|---|---|---|
| `CAML/frameworks/FLAML/venv` | 1.2GB | Phase-1 local FLAML venv (2026-07-17), stale |
| `CAML/frameworks/MLJARSupervised/venv` | 961MB | Phase-1 local MLJAR venv (2026-07-18), stale |
| `~/.cache/uv` | 3.1GB | uv's cache, shared with Ali's other uv tools; safe to clear (re-downloads on demand) |
| `CAML/.venv` | 494MB | the dev repo's orchestrator venv, used for local unit tests: keep |
