# Running CAML on a VPS

CAML is built for one Ubuntu 24.04 server: bare-metal `uv` venvs, no
Docker. The user's own machine (Windows, macOS or Linux) only drives it
over SSH. This page covers getting a server, setting it up, running commands
on it reliably, and shutting it down. The per-OS details of the user's side
are in the operator profiles: [Windows](operator-windows.md),
[macOS](operator-macos.md), [Linux](operator-linux.md).

## Choosing a server

- **x86_64, Ubuntu 24.04 LTS.** Avoid ARM: several frameworks' wheels
  (and H2O's JVM tooling) are only exercised on x86_64.
- **Dedicated vCPUs** if the provider offers them. Shared (burstable) CPUs
  make time-budgeted results noisy, because a framework that gets less CPU
  in its 5 minutes finds a worse model.
- **Sizing**: 8 vCPU / 32 GB RAM / 150 GB SSD runs the full roster on
  datasets up to roughly 100k rows × 100 columns. 4 vCPU / 16 GB / 80 GB is
  enough for small data or a handful of frameworks. Below 8 GB of RAM,
  setup adds a 4 GB swapfile, and H2O, AutoGluon and FEDOT will still hit
  out-of-memory kills on real data.
- **A GPU is optional.** CAML detects one with `nvidia-smi` and installs CUDA
  wheels for TabPFN, AutoGluon and LightAutoML. GPU runs are not yet
  verified end to end; see `docs/operations/gpu.md`.
- **Network**: the server must reach `pypi.org`, `download.pytorch.org` and
  `github.com`, plus `www.openml.org` for the OpenML benchmarks.
  `camlctl info` checks all four.

The user creates the server, because it costs money. They give it a host
alias, `caml-vps`, with key login as root (their profile's SSH section).
Never ask the user to type a password into the chat.

If the provider only gives a sudo user (for example `ubuntu`), that works
too, as long as sudo needs no password: `camlctl` re-runs itself with
`sudo -n`. Put that user in the alias's `User` line. Files then go to that
user's home, and `camlctl dataset` and `camlctl bundle` take it from there.

## Setup

From the user's machine, on any OS:

```bash
ssh caml-vps "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
ssh caml-vps "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
ssh caml-vps bash /opt/caml-src/scripts/camlctl info
ssh caml-vps bash /opt/caml-src/scripts/camlctl setup --detach
ssh caml-vps camlctl wait setup 540
```

`setup` runs `bootstrap_vps.sh` as root (an apt baseline including
`openjdk-17-jre-headless`, `build-essential` and `swig`; uv; an unprivileged
`caml` user; swap if RAM is under 8 GB; a sudoers entry that lets `caml` run
only `apt-get install`; `/usr/local/bin/camlctl`). It then runs
`setup_workspace.sh` as `caml`: a clone at `~caml/caml-workspace/CAML`,
`uv sync`, `caml doctor`. It's idempotent, so re-running it is safe. Pin a
release with `setup --ref v1.1.0`.

**From a clone, for developers** (Linux, macOS since 1.0.1, Git Bash or WSL
on Windows): `scripts/provision_vps.sh caml-vps` packages the checked-out
commit with `git archive` and pushes it over SSH, so the server needs no
GitHub access. `INCLUDE_WORKTREE=1` packages uncommitted changes too.
`scripts/sync_vps.sh caml-vps` pushes later changes and keeps the venvs and
results. It refuses to run while a `caml run` or `caml sweep` is active. A
workspace deployed this way has no `.git`, so `camlctl update` sends you back
to `sync_vps.sh`.

**By hand on the server** (as root):

```bash
git clone https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src
bash /opt/caml-src/scripts/camlctl setup
```

## Running commands on the server

Every command goes through camlctl ([camlctl.md](camlctl.md)):

```bash
ssh caml-vps camlctl caml status
ssh caml-vps camlctl start sweep caml sweep FLAML --benchmark input/datasets/churn/churn.yaml --constraint quick
ssh caml-vps camlctl status
```

Rules that have prevented real failures in this project:

- **Plain words only.** No nested quotes through ssh. Commands like
  `ssh HOST "sudo -iu caml bash -lc 'cd ... && uv run caml ...'"` broke
  repeatedly on quoting, and in different ways in PowerShell, cmd, zsh and
  bash. When you need a raw shell command, use one pair of double quotes,
  with no `$`, backtick, `%`, `!` or `"` inside.
- **Write anything longer than one command to a script file**, `scp` it
  over, and run it with `camlctl script FILE`. It runs as `caml` in the
  repo, and strips Windows line endings.
- **Detach anything that takes more than a few minutes** with
  `camlctl start JOB ...`. An SSH session that drops kills its foreground
  command, and agent shell tools time out. Then watch it with
  `camlctl wait JOB 540` or `camlctl status`.
- **Run one sweep per server.** Two drivers competing for CPU change what
  each framework achieves within its time budget, and two drivers on the
  same sweep are refused by its lock anyway.
- **Watch memory** while the first jobs run: `camlctl status` shows
  available memory, swap and OOM kills since boot.

A person at a terminal can still work interactively:
`ssh caml-vps`, then `sudo -iu caml`, `cd ~/caml-workspace/CAML` and
`uv run caml ...`.

## Several servers

`caml sweep ... --shard K/N` splits the job matrix deterministically. Run the
same command with `--shard 1/2` on one server and `--shard 2/2` on the other.
Use identical server types, since timings aren't comparable across
different CPUs. Each server writes its own `output/results.csv`, and there
is no merge command yet (known issue KI-02). Bundle both, unpack them, and
concatenate the two `results.csv` files on the server or anywhere with
pandas:

```python
import pandas as pd
pd.concat([pd.read_csv("a/output/results.csv"), pd.read_csv("b/output/results.csv")]).to_csv("merged-results.csv", index=False)
```

To rank the merged file, put it at `output/results.csv` in a scratch copy
of the repo on one server and run `caml leaderboard` there.

## Getting results off and shutting down

```bash
ssh caml-vps camlctl bundle my-results
scp caml-vps:caml-bundles/my-results.tar.gz .
```

Unpack it with `tar -xzf my-results.tar.gz` (Windows' `tar.exe` too). Then
remind the user to delete the server in their provider's console; it bills
until then. `scripts/teardown_workspace.sh caml-vps` only wipes the
workspace for a clean reinstall. It does not stop the billing.
