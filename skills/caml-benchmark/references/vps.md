# Running CAML on a VPS

CAML is built for one Ubuntu 24.04 server: bare-metal `uv` venvs, no
Docker. This page covers getting a server, provisioning it, running commands
on it reliably, and shutting it down.

## Choosing a server

- **x86_64, Ubuntu 24.04 LTS.** Avoid ARM: several frameworks' wheels
  (and H2O's JVM tooling) are only exercised on x86_64.
- **Dedicated vCPUs** if the provider offers them. Shared (burstable) CPUs
  make time-budgeted results noisy, because a framework that gets less CPU
  in its 5 minutes finds a worse model.
- **Sizing**: 8 vCPU / 32 GB RAM / 150 GB SSD runs the full roster on
  datasets up to roughly 100k rows × 100 columns. 4 vCPU / 16 GB / 80 GB is
  enough for small data or a handful of frameworks. Below 8 GB of RAM,
  `bootstrap_vps.sh` adds a 4 GB swapfile, and H2O, AutoGluon and FEDOT
  will still hit out-of-memory kills on real data.
- **A GPU is optional.** CAML detects one with `nvidia-smi` and installs CUDA
  wheels for TabPFN, AutoGluon and LightAutoML. GPU runs are not yet
  verified end to end; see `docs/operations/gpu.md`.
- **Network**: the server must reach `pypi.org`, `download.pytorch.org`,
  `github.com` and `www.openml.org`.

The user creates the server, because it costs money. Ask them for the host
(IP or name) and confirm that SSH key login works.

## SSH access (the user does this part)

If the user has no SSH key yet, they run this on their own machine:

```bash
ssh-keygen -t ed25519               # accept the defaults
ssh-copy-id root@HOST               # asks for the server's root password once
ssh -o BatchMode=yes root@HOST true && echo "key login works"
```

On a Mac, if `ssh-copy-id` is missing, append the key by hand:
`cat ~/.ssh/id_ed25519.pub | ssh root@HOST 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'`.
If the key has a passphrase, store it in the macOS keychain once
(`ssh-add --apple-use-keychain ~/.ssh/id_ed25519`), so an agent's
non-interactive `ssh` works without a prompt.

Never ask the user to type a password into the chat. The committed scripts
expect key authentication. For non-standard access (another port, a jump
host or a config alias), set `SSH="ssh -p 2222"` and `SCP="scp -P 2222"` in
front of the provisioning commands.

`provision_vps.sh` must log in as **root**, because it runs
`bootstrap_vps.sh` directly. If the provider only gives a sudo user, either
enable root key login, or use the manual route below with `sudo`.

## Provisioning

From a clone of the CAML repo on the user's machine (Linux, or macOS since
1.0.1; before that the scripts used GNU-only `mktemp` and `tar` options and
failed on a Mac):

```bash
ssh root@HOST 'curl -sS -m 20 https://www.openml.org/api/v1/json/task/3913 | head -c 120; echo'
scripts/provision_vps.sh root@HOST
```

It packages the repo (`git archive` of the checked-out commit), pushes it
over SSH, runs `bootstrap_vps.sh` as root (apt baseline including
`openjdk-17-jre-headless`, `build-essential` and `swig`; uv; an
unprivileged `caml` user; swap if RAM is under 8 GB; a sudoers entry that
lets `caml` run only `apt-get install`), then `setup_workspace.sh` as `caml`
(the workspace at `~caml/caml-workspace/CAML`, `uv sync`, `caml doctor`). It is
idempotent: re-running it is safe.

**Manual route** (run on the server as root):

```bash
git clone https://github.com/A1i-Tabatabaei/CAML.git /tmp/CAML
bash /tmp/CAML/scripts/bootstrap_vps.sh
sudo -iu caml bash /tmp/CAML/scripts/setup_workspace.sh
```

**Updating the code later** without losing installed frameworks or
results: `scripts/sync_vps.sh root@HOST` from the user's clone. It refuses to
run while a `caml run` or `caml sweep` is active on the server.

## Running commands on the server

Everything runs as `caml`, from the repo root (CAML finds its root from the
current directory):

```bash
ssh root@HOST "sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml status'"
```

Rules that have prevented real failures in this project:

- **Write anything longer than one command to a script file**, `scp` it over,
  and run the file. Long multi-line strings nested inside `ssh "..."` and
  `bash -lc '...'` have repeatedly broken on quoting.
- **Detach anything that takes more than a few minutes.** An SSH session
  that drops kills its foreground command:

  ```bash
  setsid nohup bash ~/run_sweep.sh > ~/sweep.log 2>&1 < /dev/null & disown
  ```

- **Run one sweep per server.** Two drivers competing for CPU change what
  each framework achieves within its time budget, and two drivers on the
  same sweep are refused by its lock anyway.
- **Watch memory** while the first jobs run: `free -h`, and after a `killed`
  job, `dmesg -T | grep -i -E 'killed process|oom'`.

## Several servers

`caml sweep ... --shard K/N` splits the job matrix deterministically. Run the
same command with `--shard 1/2` on one server and `--shard 2/2` on the other.
Use identical server types, since timings aren't comparable across
different CPUs. Each server writes its own `output/results.csv`, and there
is no merge command yet (known issue KI-02). Copy both files back and
concatenate them:

```bash
uv run python -c "import pandas as pd, sys; pd.concat([pd.read_csv(f) for f in sys.argv[1:]]).to_csv('merged-results.csv', index=False)" a/results.csv b/results.csv
```

To rank the merged file, put it at `output/results.csv` in a scratch copy
of the repo and run `caml leaderboard` there.

## Getting results off and shutting down

```bash
scp -r root@HOST:/home/caml/caml-workspace/CAML/output ./caml-output     # from the user's machine
```

Then remind the user to delete the server in their provider's console; it
bills until then. `scripts/teardown_workspace.sh root@HOST` only wipes the
workspace for a clean reinstall. It does not stop the billing.
