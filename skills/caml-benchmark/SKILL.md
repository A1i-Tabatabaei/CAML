---
name: caml-benchmark
description: Benchmark the major open-source AutoML frameworks (AutoGluon, H2O AutoML, FLAML, LightAutoML, MLJAR, TPOT, GAMA, FEDOT, SapientML, TabPFN) on a user's own tabular dataset with CAML, and report which one does best. Use when the user wants to train or compare AutoML models on their CSV/Parquet data, asks "which AutoML is best for my dataset", wants to run AMLB/OpenML AutoML benchmarks, or mentions CAML. Works from Windows, macOS or Linux; CAML itself always runs on an Ubuntu VPS, driven over SSH with one quote-free command (camlctl). Covers the VPS, preparing the data, the TabPFN API token, running and monitoring sweeps, reading the results honestly, a field report of problems hit, and citing CAML.
license: Apache-2.0
metadata:
  version: "1.1.0"
  repository: https://github.com/A1i-Tabatabaei/CAML
---

# Benchmark AutoML frameworks on a dataset with CAML

CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework
into its own isolated `uv` environment on an Ubuntu server, runs them all on
the same folds of the same data, scores them with the same code, and ranks
them. This skill takes a user from "here is my CSV" to a ranked,
reproducible comparison.

**Where things run.** You (the agent) run on the user's machine: Windows,
macOS or Linux. CAML always runs on an **Ubuntu 24.04 server**. You drive it
with one command shape, the same on every OS:

```bash
ssh caml-vps camlctl <command> [plain words]
```

`camlctl` ([references/camlctl.md](references/camlctl.md)) runs as the
`caml` user in the repo, detaches long jobs, reports status, takes in the
dataset and bundles the results, so you never nest quotes through ssh.

Follow the phases in order. Each one ends with a check; don't move on until
it passes. Where a step needs the user's decision, money or secrets, stop and
ask.

## Ground rules

1. **Secrets never go through chat.** Never ask the user to paste a password,
   SSH key or the `TABPFN_TOKEN` into the conversation, and never echo, log or
   commit one. Give the user the command to run themselves
   (`ssh -t caml-vps camlctl tabpfn-token` prompts silently).
2. **The user's data stays where they allow.** Copying it to their own
   server is part of the job, but confirm they're fine with that first. Never
   send it anywhere else. `TabPFNClient` uploads the data to Prior Labs'
   servers: include it **only** after the user explicitly agrees
   ([references/tabpfn.md](references/tabpfn.md)).
3. **Money is the user's call.** Renting a VPS costs money. Recommend a size,
   but let the user create it and give you the host. Remind them to delete
   it when you're done.
4. **Install nothing on the user's machine.** Frameworks are tens of GB,
   and timings only mean something on the server. Locally you use `ssh`,
   `scp`, your file tools, and at most a read-only `git clone` of CAML.
5. **Report honestly.** Failed frameworks are results: report them with
   their error and never drop them silently. Never claim significance that
   the statistics don't support (see Phase 7).
6. **Keep a field report.** From your first command, record every problem,
   workaround and gotcha in `caml-field-report-<os>.md`
   ([references/field-report.md](references/field-report.md)). It is how
   CAML gets fixed for the next user on this OS.

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

## Phase 1: Know your machine, reach the server

**Find out which OS and shell you're in**, with one command. Your
environment notes may already say.

| You see | You are on | Read |
|---|---|---|
| `uname -s` prints `Darwin` | macOS | [references/operator-macos.md](references/operator-macos.md) |
| `uname -s` prints `Linux` | Linux, or WSL if `/proc/version` mentions `microsoft` | [references/operator-linux.md](references/operator-linux.md) |
| `uname -s` prints `MINGW64_NT-...` or `MSYS_NT-...` | Windows, Git Bash | [references/operator-windows.md](references/operator-windows.md) |
| `$PSVersionTable.PSVersion` prints a version (`uname` fails) | Windows, PowerShell | [references/operator-windows.md](references/operator-windows.md) |
| `/usr/local/bin/camlctl` exists and this is the server | The CAML server itself | Skip SSH: run `camlctl ...` directly as root |

Read that profile before continuing. It has the local commands (hashing,
copying, unpacking), the SSH setup, and the OS's gotchas. Then start the
field report.

**Server size** (tell the user; they create it with any provider):

| Use | vCPU | RAM | Disk |
|---|---|---|---|
| Up to ~100k rows × 100 columns, full roster | 8 dedicated, x86_64 | 32 GB | 150 GB SSD |
| Small data / a few frameworks | 4 | 16 GB | 80 GB |
| Floor (expect swapping and memory failures) | 4 | 8 GB | 50 GB |

As a rule of thumb, RAM should be at least 10× the CSV's size. Ubuntu 24.04,
root (or a passwordless sudoer) over SSH. No GPU is needed; if one is there,
CAML uses it for TabPFN, AutoGluon and LightAutoML.

**SSH**: the profile's check must print `ok` with no prompt:
`ssh -o BatchMode=yes caml-vps echo ok`. If it doesn't, walk the user
through the profile's SSH section; they type the server password themselves.

## Phase 2: Set up the server

```bash
ssh caml-vps "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
ssh caml-vps "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
ssh caml-vps bash /opt/caml-src/scripts/camlctl info
```

`info` reports the OS, architecture, CPUs, RAM, disk and network, ending with
`checks: ok` or a list of warnings. Compare it with the sizing table and
tell the user about any warning. `net_pypi`, `net_github` and `net_pytorch`
must be `ok`. `net_openml` only matters for the OpenML benchmarks, not for
the user's own data. If `caml:` already shows a version, CAML is set up:
skip to the check below.

```bash
ssh caml-vps bash /opt/caml-src/scripts/camlctl setup --detach
ssh caml-vps camlctl wait setup 540
```

Setup takes 5–15 minutes. Repeat `wait` while it exits 124 (still running).
It installs the apt baseline, uv, the unprivileged `caml` user, swap below
8 GB of RAM, the workspace at `~caml/caml-workspace/CAML`, `/usr/local/bin/camlctl`
and `~caml/data`. It's idempotent.

**Check**: `ssh caml-vps camlctl version` shows a CAML version, and
`ssh caml-vps camlctl caml doctor` prints no `MISSING`.

(Developers deploying a local, uncommitted checkout use
`scripts/provision_vps.sh caml-vps` from Linux, macOS, Git Bash or WSL
instead; see [references/vps.md](references/vps.md).)

## Phase 3: Install the frameworks

```bash
ssh caml-vps camlctl start install install AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML
ssh caml-vps camlctl wait install 540
```

This takes 30–60 minutes. Install only what you'll run, and never include
`NaiveAutoML` (an upstream bug fails every task). The job ends with
`installed: ...` and `failed: ...` lines. Retry a failure once with
`ssh caml-vps camlctl install --force NAME`, then check
[references/troubleshooting.md](references/troubleshooting.md). One failed
framework doesn't block the others.

**Smoke test**, if `info` showed OpenML reachable: one fast framework, before
committing hours:

```bash
ssh caml-vps camlctl start smoke caml run FLAML --benchmark test --constraint test
ssh caml-vps camlctl wait smoke 540
```

It takes about 6 minutes and must print real scores, not NaN.

**TabPFN** needs the token first: follow
[references/tabpfn.md](references/tabpfn.md). Skip TabPFN if the user has no
token.

## Phase 4: Prepare the data

Upload the file under a simple name (no spaces), then let `camlctl` take it
in. The profile shows the local `scp` and hash commands for your OS:

```bash
scp "/path/on/your/machine/My Data.csv" caml-vps:churn.csv
ssh caml-vps camlctl dataset churn.csv
```

`dataset` moves the file to `~caml/data/` (readable only by `caml`) and
prints its `sha256` (compare it with your local hash), encoding, separator,
columns, rows and header, ending with `status:`:

- `ok`: continue.
- `needs-conversion`: the file isn't UTF-8. It's usually an Excel export on
  Windows (`--from-encoding WINDOWS-1252`), or an old Mac export
  (`--from-encoding MACINTOSH`). Ask the user if unsure, then run the
  printed `fix:` command.
- `unsupported`: an `.xlsx` workbook. Ask the user to export a CSV UTF-8.

Then split it:

```bash
ssh caml-vps camlctl caml prepare-data /home/caml/data/churn.csv --target churned --drop customer_id --name churn --folds 5
```

`prepare-data` prints the task type and why it chose it, the class counts,
and warnings. **Read them back to the user and confirm the task type.** Fix
it with `--type binary|multiclass|regression` if it's wrong. It reads
semicolon-separated files and decimal commas (`1,5`). Useful options:

| Option | Use |
|---|---|
| `--folds 5` (default) | Stratified k-fold for classification, plain k-fold for regression |
| `--folds 1 --test-size 0.2` | One holdout split, for big data or a tight budget |
| `--drop COL` (repeatable) | Remove IDs and leaky columns |
| `--name NAME` | The task name in results (default: the file name) |
| `--seed N` | A different split (default 42; record it) |
| `--force` | Overwrite an earlier preparation of the same name |

It writes `input/datasets/<name>/` in the repo: the fold CSVs, `<name>.yaml`
(the benchmark definition) and `dataset.json` (the source's SHA-256, row
counts and seed). From now on, pass `--benchmark input/datasets/<name>/<name>.yaml`.
Details, validation errors and the manual YAML format are in
[references/data-preparation.md](references/data-preparation.md).

## Phase 5: Run and monitor the sweep

Choose the frameworks. The default is everything installed, minus the two
special cases:

```text
AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML
```

- Add `TabPFN` if the token is set. On a CPU-only server it refuses more than
  1,000 training rows (a GPU lifts this); otherwise it just shows up as failed folds.
- Add `TabPFNClient` **only** if the user agreed to upload this data to Prior Labs.
- Never include `NaiveAutoML`.

Choose the constraint (the per-job budget):

| Constraint | Per job | When |
|---|---|---|
| `quick` | 5 min, all cores | First screening (the default recommendation) |
| `test` | 10 min, 4 cores | Small boxes |
| `1h8c` | 1 hour, 8 cores | The final comparison of the top frameworks, as in AMLB's papers |

Preview the job matrix, then launch it as a job:

```bash
ssh caml-vps camlctl caml sweep AutoGluon FLAML TPOT --benchmark input/datasets/churn/churn.yaml --constraint quick --dry-run
ssh caml-vps camlctl start sweep caml sweep AutoGluon FLAML TPOT --benchmark input/datasets/churn/churn.yaml --constraint quick
```

Tell the user the start time (UTC), the number of jobs and the ETA.

**Monitor** without disturbing it. CPU contention changes results, so start
no other heavy work on the box.

```bash
ssh caml-vps camlctl status
ssh caml-vps camlctl wait sweep 540
```

`status` shows load, memory, swap, disk, OOM kills, every job, the sweep's
latest progress line and its status table (`PENDING`, `OK`, `ERROR`, ...).
`wait` blocks on the server until the sweep ends or the time passes. Check
every 20–30 minutes (use your scheduler if you have one, or a
`wait` that fits your tool's timeout), not in a tight loop. Keep a
`monitoring-log.md` in the report folder: time, jobs done, failures, memory,
and what you did.

**Recover**: `camlctl start sweep caml sweep ...` with the exact same
arguments resumes and skips finished jobs (`lost` in `camlctl jobs` means the
server rebooted). After fixing a cause, add `--retry-failed`; ask the user
first if it re-runs more than an hour of jobs. With two servers, split the
work with `--shard 1/2` and `--shard 2/2`.

## Phase 6: Triage failures

For every job whose status isn't `ok`, find out why before reporting:

| Status | Usual cause | Look at |
|---|---|---|
| `error` | The framework raised an exception | The ledger's `detail`, `output/sweeps/<sweep>/logs/<fw>.<task>.<fold>.log` |
| `killed` | Out of memory (the kernel OOM killer) | `camlctl status` (OOM kills), the job log |
| `timeout` | The framework ignored its time budget, or hung | The job log's last lines |
| `crash` / `no_result` | A crash before any result, or a CAML bug | The job log; report a CAML bug upstream |

A job log's path has no special characters, so a plain double-quoted
command reads it from any shell:
`ssh caml-vps "tail -n 60 /home/caml/caml-workspace/CAML/output/sweeps/churn-quick/logs/FLAML.churn.0.log"`.
The bundle (Phase 7) has every log too.

Classify each failure as **a framework limitation** (report it), **a budget
or memory limit** (report it, or re-run with more), or **a CAML bug** (put it
in the field report, and draft an issue for
https://github.com/A1i-Tabatabaei/CAML/issues with the log tail). Common
cases and fixes are in
[references/troubleshooting.md](references/troubleshooting.md).

## Phase 7: Report the results

```bash
ssh caml-vps camlctl caml leaderboard --benchmark input/datasets/churn/churn.yaml --constraint quick --markdown
ssh caml-vps camlctl bundle churn-results
scp caml-vps:caml-bundles/churn-results.tar.gz .
```

Unpack the bundle with the profile's `tar` command. It holds `output/`
(results, sweep ledgers, per-job logs), `datasets/` (the folds, YAML and
`dataset.json`), `jobs/` (camlctl's job logs) and `server-info.txt`.

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

## Phase 8: Clean up

Ask before deleting anything. Tell the user what's left on the server (the
frameworks, their data in `~caml/data`, the prepared folds, the outputs) and
ask whether to delete their data there. Remind them to **delete the VPS** in
their provider's console; it bills while it exists. If they'll reuse it,
`camlctl update` updates the code later and keeps the installed frameworks.

## Phase 9: Hand over the field report

Finish `caml-field-report-<os>.md` (Summary, "What worked first time"), make
sure it has no secrets, IPs or data rows, and tell the user where it is and
that it's meant for the CAML maintainer, via a GitHub issue with the "Field
report" template. Don't post it yourself.

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
  version = {1.1.0},
  url     = {https://github.com/A1i-Tabatabaei/CAML},
  license = {Apache-2.0}
}
```

Plain text: Tabatabaei, A. (2026). *CAML: Benchmarking open-source AutoML
frameworks in isolated environments* (Version 1.1.0) [Computer software].
https://github.com/A1i-Tabatabaei/CAML

AMLB: Gijsbers, P., Bueno, M. L. P., Coors, S., LeDell, E., Poirier, S.,
Thomas, J., Bischl, B., & Vanschoren, J. (2024). AMLB: an AutoML Benchmark.
*Journal of Machine Learning Research*, 25(101), 1–65.

## Quick reference

Every line runs from the user's machine, on any OS.

| Step | Command |
|---|---|
| Server facts | `ssh caml-vps camlctl info` |
| Set up (detached) | `ssh caml-vps bash /opt/caml-src/scripts/camlctl setup --detach` |
| Health check | `ssh caml-vps camlctl caml doctor` |
| Install frameworks (detached) | `ssh caml-vps camlctl start install install AutoGluon FLAML ...` |
| What's installed | `ssh caml-vps camlctl caml status` |
| Take in the data | `scp FILE caml-vps:NAME.csv`, then `ssh caml-vps camlctl dataset NAME.csv` |
| Prepare data | `ssh caml-vps camlctl caml prepare-data /home/caml/data/NAME.csv --target COL --name NAME` |
| Preview a sweep | `ssh caml-vps camlctl caml sweep FW... --benchmark YAML --constraint quick --dry-run` |
| Run a sweep (detached) | `ssh caml-vps camlctl start sweep caml sweep FW... --benchmark YAML --constraint quick` |
| Monitor | `ssh caml-vps camlctl status`, `ssh caml-vps camlctl wait sweep 540` |
| A job's log | `ssh caml-vps camlctl logs sweep 100` |
| Rank | `ssh caml-vps camlctl caml leaderboard --benchmark YAML --markdown` |
| Results to your machine | `ssh caml-vps camlctl bundle NAME`, then `scp caml-vps:caml-bundles/NAME.tar.gz .` |
| Compare across 2+ datasets | `ssh caml-vps camlctl caml compare FW1 FW2 ... --constraint quick` |
| TabPFN key (the user runs it) | `ssh -t caml-vps camlctl tabpfn-token` |
