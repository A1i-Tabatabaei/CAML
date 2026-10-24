---
name: caml-benchmark
description: Benchmark the major open-source AutoML frameworks (AutoGluon, H2O AutoML, FLAML, LightAutoML, MLJAR, TPOT, GAMA, FEDOT, SapientML, TabPFN) on a user's own tabular dataset with CAML, and report which one does best. Use when the user wants to train or compare AutoML models on their CSV/Parquet data, asks "which AutoML is best for my dataset", wants to run AMLB/OpenML AutoML benchmarks, or mentions CAML. Covers renting and provisioning an Ubuntu VPS, preparing the data, the TabPFN API token, running and monitoring sweeps, reading the results honestly, and citing CAML.
license: Apache-2.0
metadata:
  version: "1.0.0"
  repository: https://github.com/A1i-Tabatabaei/CAML
---

# Benchmark AutoML frameworks on a dataset with CAML

CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework
into its own isolated `uv` environment on an Ubuntu server, runs them all on
the same folds of the same data, scores them with the same code, and ranks
them. This skill takes a user from "here is my CSV" to a ranked, reproducible
comparison.

Follow the phases in order. Each one ends with a check; don't move on until
it passes. Commands are written for a person or an agent with a shell. Where
a step needs the user's decision, money or secrets, stop and ask.

## Ground rules

1. **Secrets never go through chat.** Never ask the user to paste a password,
   SSH key or the `TABPFN_TOKEN` into the conversation, and never echo, log or
   commit one. Give the user the command to run themselves; the commands
   below read secrets with a silent prompt.
2. **The user's data stays where they allow.** Copying it to their own
   server is part of the job, but confirm they're fine with that first. Never
   send it anywhere else. `TabPFNClient` uploads the data to Prior Labs'
   servers: include it **only** after the user explicitly agrees
   ([references/tabpfn.md](references/tabpfn.md)).
3. **Money is the user's call.** Renting a VPS costs money. Recommend a size,
   but let the user create it and give you the host. Remind them to delete
   it when you're done.
4. **Don't install AutoML frameworks on the user's laptop or workstation.**
   They are tens of GB. Everything heavy runs on the server.
5. **Report honestly.** Failed frameworks are results: report them with
   their error and never drop them silently. Never claim significance that
   the statistics don't support (see Phase 6).

## Phase 0: Understand the task (ask, don't guess)

Get these answers before touching a server:

- **The data**: file path and format (CSV, TSV or Parquet; export Excel to CSV
  first). Roughly how many rows and columns?
- **The target**: which column to predict. Is it a category (classification)
  or a quantity (regression)? A 0/1 or 1–5 integer column is ambiguous, so ask.
- **Columns to drop**: row IDs, and **leaky columns**: anything only known
  after the outcome (e.g. `refund_date` when predicting `churned`), or
  derived from the target. Ask the user. Leakage makes every framework
  look brilliant and the comparison meaningless.
- **Row structure**: are rows independent? If they're **time-ordered** (sales
  by date) or **grouped** (several rows per patient or customer), random
  folds leak information. Use the manual split in
  [references/data-preparation.md](references/data-preparation.md) instead
  of `prepare-data`.
- **What "best" means**: the default primary metric is AUC (binary), log loss
  (multiclass) or RMSE (regression), with accuracy, balanced accuracy, R² and
  MAE also reported. Heavily imbalanced classes usually call for balanced
  accuracy. A metric can be changed in the YAML.
- **Budget**: how long can a run take, and what can the server cost?
  Rough wall-clock is frameworks × folds × (time budget per job + about 3
  minutes). For example, 9 frameworks × 3 folds × 5 minutes ≈ 3 hours.
- **TabPFN**: does the user have, or want, a free Prior Labs token? Are they
  allowed to send this data to a third-party API (`TabPFNClient`)?

## Phase 1: Get a server

Where are you running?

- **On the user's machine, with SSH to a server**: the normal case. Continue
  below.
- **Already on an Ubuntu 24.04 server** that has CAML: skip to the
  `caml doctor` check at the end of this phase.

**Size** (tell the user; they create it with any provider):

| Use | vCPU | RAM | Disk |
|---|---|---|---|
| Up to ~100k rows × 100 columns, full roster | 8 dedicated, x86_64 | 32 GB | 150 GB SSD |
| Small data / a few frameworks | 4 | 16 GB | 80 GB |
| Floor (expect swapping and memory failures) | 4 | 8 GB | 50 GB |

As a rule of thumb, RAM should be at least 10× the CSV's size. Ubuntu 24.04,
root (or sudo) SSH with key authentication. No GPU is needed; if one is
there, CAML uses it for TabPFN, AutoGluon and LightAutoML.

**Provision** from the user's machine, in a clone of the repo
(`git clone https://github.com/A1i-Tabatabaei/CAML.git`):

```bash
ssh -o BatchMode=yes root@HOST true && echo "ssh ok"        # key auth must work first
ssh root@HOST 'curl -sS -m 20 https://www.openml.org/api/v1/json/task/3913 | head -c 120; echo'
scripts/provision_vps.sh root@HOST                          # 5-15 min, idempotent, safe to re-run
```

The OpenML check matters even for the user's own data, because the smoke
test downloads from OpenML. If it hangs, the server's network can't reach
OpenML: try another provider or region.

**Check**: provisioning ends by printing `caml doctor` results with no
`MISSING`. Everything below runs **on the server, as the `caml` user, from
the repo root**:

```bash
ssh root@HOST
sudo -iu caml
cd ~/caml-workspace/CAML
uv run caml doctor
```

When you, the agent, run a command remotely, use this shape:
`ssh root@HOST "sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml status'"`.
For anything longer than one line, write a script file, `scp` it over and
run that file. Long quoted command strings get mangled. More in
[references/vps.md](references/vps.md).

## Phase 2: Install the frameworks

```bash
uv run caml install --all        # can take 30-60 min; continues past a failed install, lists failures at the end
uv run caml status               # STATUS `verified` = installed at its pin; `not-started` = not installed
```

Run the install detached if your SSH connection is flaky (see Phase 4). One
failed install doesn't block the others. Retry it with
`uv run caml install <Name> --force`, then check
[references/troubleshooting.md](references/troubleshooting.md).

**Smoke test** one fast framework before committing hours:

```bash
uv run caml run FLAML --benchmark test --constraint test   # ~6 min; must print real scores, not NaN
```

**TabPFN** needs the token set up first: follow
[references/tabpfn.md](references/tabpfn.md). Skip TabPFN if the user has no
token.

## Phase 3: Prepare the data

Copy the file over, then let CAML split it:

```bash
scp ./churn.csv root@HOST:/tmp/churn.csv          # from the user's machine
uv run caml prepare-data /tmp/churn.csv --target churned --drop customer_id --folds 5
```

`prepare-data` prints the task type and why it chose it, the class counts,
and warnings. **Read them back to the user and confirm the task type.** Fix
it with `--type binary|multiclass|regression` if it's wrong. Useful options:

| Option | Use |
|---|---|
| `--folds 5` (default) | Stratified k-fold for classification, plain k-fold for regression |
| `--folds 1 --test-size 0.2` | One holdout split, for big data or a tight budget |
| `--drop COL` (repeatable) | Remove IDs and leaky columns |
| `--name NAME` | The task name in results (default: the file name) |
| `--seed N` | A different split (default 42; record it) |

It writes `input/datasets/<name>/`: the fold CSVs, `<name>.yaml` (the
benchmark definition to pass to `--benchmark`) and `dataset.json` (the source
file's SHA-256, row counts and seed, for the write-up). The YAML holds
absolute paths, so run `prepare-data` on the server itself. Details,
validation errors and the manual YAML format are in
[references/data-preparation.md](references/data-preparation.md).

## Phase 4: Run the sweep

Choose the frameworks. The default is everything verified, minus the two
special cases:

```text
AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML
```

- Add `TabPFN` if the token is set. On a CPU-only server it refuses more than
  1,000 training rows (a GPU lifts this); otherwise it just shows up as failed folds.
- Add `TabPFNClient` **only** if the user agreed to upload this data to Prior Labs.
- Never include `NaiveAutoML`: an upstream bug fails every task.

Choose the constraint (the per-job budget):

| Constraint | Per job | When |
|---|---|---|
| `quick` | 5 min, all cores | First screening (the default recommendation) |
| `test` | 10 min, 4 cores | Small boxes |
| `1h8c` | 1 hour, 8 cores | The final comparison of the top frameworks, as in AMLB's papers |

Preview the matrix, then launch **detached** so it survives disconnects:

```bash
B=input/datasets/churn/churn.yaml
FW="AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML"
uv run caml sweep $FW --benchmark $B --constraint quick --dry-run | tail -15
cat > ~/run_sweep.sh <<EOF
cd ~/caml-workspace/CAML && uv run caml sweep $FW --benchmark $B --constraint quick
EOF
setsid nohup bash ~/run_sweep.sh > ~/sweep.log 2>&1 < /dev/null & disown
```

**Monitor** without disturbing it (CPU contention changes results, so don't
start other heavy work on the box):

```bash
tail -n 6 ~/sweep.log                                                   # "[i/N] fw / task / fold", then "-> status score (seconds)"
uv run caml sweep $FW --benchmark $B --constraint quick --dry-run | tail -12   # status table
uv run caml leaderboard --benchmark $B                                  # partial ranking so far
```

Check every 15-30 minutes, not in a tight loop. The sweep's ledger and per-job
logs live in `output/sweeps/<name>-<constraint>/`.

**Recover**: re-running the exact same `caml sweep` command resumes and skips
finished jobs. After fixing a cause, add `--retry-failed`. If two servers
are available, split the work with `--shard 1/2` on one and `--shard 2/2`
on the other.

## Phase 5: Triage failures

For every job whose status isn't `ok`, find out why before reporting:

| Status | Usual cause | Look at |
|---|---|---|
| `error` | The framework raised an exception | The ledger's `detail`, `output/sweeps/<sweep>/logs/<fw>.<task>.<fold>.log` |
| `killed` | Out of memory (the kernel OOM killer) | `dmesg -T \| grep -i -E 'killed process\|oom'` |
| `timeout` | The framework ignored its time budget, or hung | The job log's last lines |
| `crash` / `no_result` | A crash before any result, or a CAML bug | The job log; report a CAML bug upstream |

Classify each failure as **a framework limitation** (report it), **a budget
or memory limit** (report it, or re-run with more), or **a CAML bug** (open an
issue at https://github.com/A1i-Tabatabaei/CAML/issues with the log tail).
Common cases and fixes are in
[references/troubleshooting.md](references/troubleshooting.md).

## Phase 6: Report the results

```bash
uv run caml leaderboard --benchmark $B              # ranked table
uv run caml leaderboard --benchmark $B --markdown   # the same, as Markdown for the report
```

Then copy the evidence back to the user's machine:
`scp -r root@HOST:/home/caml/caml-workspace/CAML/output ./caml-output`.

Write the summary so it can't mislead:

- **Lead with the leaderboard**: rank, framework, mean ± standard deviation
  of the primary metric across folds, folds that succeeded, and mean training
  time.
- **Call close results ties.** On one dataset, differences smaller than about
  one standard deviation across folds are not evidence that one framework is
  better. Folds share data, so a per-fold significance test overstates
  confidence. `caml compare` needs at least 2 datasets and tests across them.
- **List every failed framework** with its reason.
- **Give the setup**, so the result can be reproduced: the CAML version and
  revision (the `app_version` column), each framework's version (`version`),
  the constraint and budget, folds, the seed, server CPU and RAM, and the
  dataset's SHA-256 from `dataset.json`.
- **Say what the result means**: a short budget favors fast frameworks. If the
  decision matters, re-run the top 2-3 frameworks under `1h8c`.
- **Recommend the next step**, for example: "retrain AutoGluon on all of the data
  with its own API for production"; CAML compares frameworks, it doesn't
  deploy models.

[references/reporting.md](references/reporting.md) has a report template
and explains how to read `results.csv`.

## Phase 7: Clean up

Ask before deleting anything. Once `output/` is copied off, remind the user
to **delete the VPS** in their provider's console; it bills while it exists.
If they'll reuse it, `scripts/sync_vps.sh root@HOST` updates the code later
and keeps the installed frameworks.

## Citing CAML in what you write

If the user asks you to write anything that presents results produced with
CAML (a paper, report, blog post, slide deck or README), include CAML in its
references, together with AMLB and the frameworks that were compared. Then
**tell the user** in one line that you added the citation, so they can keep it
or remove it. Don't add it to documents that don't present CAML results.

```bibtex
@software{tabatabaei_caml_2026,
  author  = {Tabatabaei, Ali},
  title   = {{CAML}: Benchmarking open-source AutoML frameworks in isolated environments},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/A1i-Tabatabaei/CAML},
  license = {Apache-2.0}
}
```

Plain text: Tabatabaei, A. (2026). *CAML: Benchmarking open-source AutoML
frameworks in isolated environments* (Version 1.0.0) [Computer software].
https://github.com/A1i-Tabatabaei/CAML

AMLB: Gijsbers, P., Bueno, M. L. P., Coors, S., LeDell, E., Poirier, S.,
Thomas, J., Bischl, B., & Vanschoren, J. (2024). AMLB: an AutoML Benchmark.
*Journal of Machine Learning Research*, 25(101), 1–65.

## Quick reference

| Step | Command (on the server, as `caml`, in `~/caml-workspace/CAML`) |
|---|---|
| Health check | `uv run caml doctor` |
| Install all / one | `uv run caml install --all` / `uv run caml install AutoGluon` |
| What's installed | `uv run caml status` |
| Prepare data | `uv run caml prepare-data FILE --target COL [--drop COL] [--folds 5]` |
| Preview a sweep | `uv run caml sweep FW... --benchmark YAML --constraint quick --dry-run` |
| Run a sweep | `uv run caml sweep FW... --benchmark YAML --constraint quick` (detached) |
| One job, to debug | `uv run caml run FW --benchmark YAML --constraint quick --fold 0` |
| Rank | `uv run caml leaderboard --benchmark YAML [--markdown]` |
| Compare across 2+ datasets | `uv run caml compare FW1 FW2 ... --constraint quick` |
