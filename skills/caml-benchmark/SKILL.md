---
name: caml-benchmark
description: Benchmark the major open-source AutoML frameworks (AutoGluon, H2O AutoML, FLAML, LightAutoML, MLJAR, TPOT, GAMA, FEDOT, SapientML, TabPFN) on a user's own tabular dataset with CAML, and report which one does best. Use when the user wants to train or compare AutoML models on their CSV/Parquet data, asks "which AutoML is best for my dataset", wants to run AMLB/OpenML AutoML benchmarks, or mentions CAML. Works from Windows, macOS or Linux; CAML itself always runs on an Ubuntu VPS, driven over SSH with one quote-free command (camlctl). Covers three required check-ins with the user (the goal: a benchmark study or the best model; API keys entered by the user, never through chat; the task, confirmed after probing the data without reading its values), the VPS, anonymizing and preparing the data, running and monitoring sweeps, reading the results honestly, a field report of problems hit, and citing CAML.
license: Apache-2.0
metadata:
  version: "1.2.0"
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
ask. Three of those stops are fixed, and you never skip them:

| Check-in | When | Details |
|---|---|---|
| **1. The goal**: a benchmark study (the comparison is the result, for an article or report), or the best model (for the rest of their project)? | Your first message (Phase 0) | [checkpoints.md §1](references/checkpoints.md#1-the-goal-benchmark-study-or-best-model) |
| **2. Credentials**: the user enters API keys on the server themselves | Right after setup (Phase 2) | [checkpoints.md §2](references/checkpoints.md#2-credentials-keys-go-to-the-server-never-through-chat) |
| **3. The task**: target, task type, features, row structure and metric, confirmed by the user after you probe the data | Before `prepare-data` (Phase 4) | [checkpoints.md §3](references/checkpoints.md#3-the-task-probe-then-confirm) |

## Ground rules

1. **Secrets never go through chat.** Never ask the user to paste a password,
   SSH key or API key (`TABPFN_TOKEN`, ...) into the conversation, never put
   one on a command line, and never echo, log, read or commit one. The user
   enters keys themselves: `ssh -t caml-vps camlctl secrets` (input hidden),
   or a `caml-secrets.env` file they fill in and you import unread
   ([checkpoints.md §2](references/checkpoints.md#2-credentials-keys-go-to-the-server-never-through-chat)).
2. **The user's data stays where they allow, and out of your context.**
   Copying it to their own server is part of the job, but confirm they're
   fine with that first, and remove personal data first if they want
   ([checkpoints.md §3a](references/checkpoints.md#3a-personal-data-first)).
   Never send it anywhere else. Probe it with `camlctl caml describe-data`,
   which prints no cell values, rather than `head` or `cat`. `TabPFNClient`
   uploads the data to Prior Labs' servers: include it **only** after the
   user explicitly agrees ([references/tabpfn.md](references/tabpfn.md)).
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
7. **The user decides the goal and the task.** You probe, guess and
   propose. They confirm. Never start a sweep on a task the user hasn't
   confirmed.

## Phase 0: Ask before you plan (check-in 1: the goal)

Your first message, before you change anything on the server, covers:

- **The goal** (check-in 1). Ask whether this is a **benchmark study** (the
  comparison itself is the result: they'll write about it in an article,
  thesis or report) or about finding **the best model** to use in the rest
  of their project, or both. Use the template in
  [checkpoints.md §1](references/checkpoints.md#1-the-goal-benchmark-study-or-best-model).
  If the prompt already says, confirm it in one line. The answer decides the
  frameworks, folds, budget and report:

  | | Benchmark study | Best model |
  |---|---|---|
  | Frameworks | All that can run, identical budgets, failures reported | Screen all, then the top 2–3 |
  | Folds | 10 (5 on small data or a tight budget) | 5 |
  | Budget | One constraint for all (`1h8c` if affordable) | `quick` screen, then `1h8c` for the top 2–3 |
  | Report | Methods, full leaderboard, failures, citations | The winner, ties, trade-offs, how to use it |

- **The data**: file path and format (CSV, TSV or Parquet; export Excel to
  CSV first). Roughly how many rows and columns? **Does it contain personal
  data, and has it been anonymized?** ([checkpoints.md §3a](references/checkpoints.md#3a-personal-data-first)).
  Are they fine with it being copied to their server?
- **What they want to predict**, if they know. Don't settle the details
  yet: the task card in Phase 4 does that, after you've probed the data.
- **Budget**: how long can a run take, and what can the server cost?
  Rough wall-clock is frameworks × folds × (time budget per job + about 3
  minutes). For example, 9 frameworks × 5 folds × (5 + 3) minutes ≈ 6 hours.
- **TabPFN**: do they want it (it needs a free Prior Labs key, entered at
  check-in 2)? Are they allowed to send this data to a third-party API
  (`TabPFNClient`)?
- **Your plan** in under 10 lines (frameworks, folds, constraint, estimated
  duration, which keys you'll need), shaped by the goal.

Wait for the user's OK before Phase 2 changes anything on the server.

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

**Check-in 2: credentials**, as soon as setup is done (start the installs
first if you like; they don't need keys):

```bash
ssh caml-vps camlctl secrets --check
```

If the plan needs a key that isn't `set` (TabPFN needs `TABPFN_TOKEN`), ask
the user to run `ssh -t caml-vps camlctl secrets` **in their own terminal**.
It asks for each key with the input hidden. Or, if they prefer an editor,
create `caml-secrets.env` from `camlctl secrets --template` for them to fill
in, then upload it and `camlctl secrets --import` it, which deletes the
uploaded copy, and delete the local one. Never read that file once they've
filled it in. The steps and message templates are in
[checkpoints.md §2](references/checkpoints.md#2-credentials-keys-go-to-the-server-never-through-chat).
Finish with `--check` again. If there's no key, take TabPFN out of the plan.

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

**TabPFN** needs `TABPFN_TOKEN` (check-in 2) and the user's decisions in
[references/tabpfn.md](references/tabpfn.md). Skip TabPFN if the user has no
key.

## Phase 4: The data (check-in 3: the task)

**Upload** the file under a simple name (no spaces), then let `camlctl` take
it in. The profile shows the local `scp` and hash commands for your OS:

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

**Probe** it without reading its values:

```bash
ssh caml-vps camlctl caml describe-data /home/caml/data/churn.csv
```

It numbers the columns and gives each one a kind, missing share, distinct
count and flags (`pii?`, `id-like`, `group-id?`, `date`, `free-text`,
`constant`), then `target_candidates` with the task type each implies. It
prints no cell values. Don't use `head`, `cat` or a script that prints rows.

**Remove personal data** if it isn't anonymized yet and the user wants it
gone (Phase 0). Show them the `pii?` and `id-like` columns, agree what to
drop and what to hash, then:

```bash
ssh caml-vps camlctl caml anonymize-data /home/caml/data/churn.csv --drop 2 --drop email --hash customer_id --out /home/caml/data/churn-anon.csv --delete-original
```

Columns go by name, or by number when the name has spaces or symbols. It
removes direct identifiers only. Combinations of ordinary columns can still
identify people, so tell the user that
([checkpoints.md §3b](references/checkpoints.md#3b-upload-then-remove-identifiers)).

**Guess, then confirm the task (check-in 3).** Run `describe-data` again with
the likely target. That adds its class labels and counts (the only values it
prints), `leak?` flags, the default metric, imbalance advice, `suggest_drop`
and `ask_user`:

```bash
ssh caml-vps camlctl caml describe-data /home/caml/data/churn-anon.csv --target Churn
```

Then send the user the **task card** and wait for "confirmed": the target
(y) and what it means, the task type (binary, multiclass or regression), the
feature columns (X), with each column you'd leave out and why, whether all
the other features should be used, how rows relate (independent, grouped or
ordered in time), the metric, and any rows left out. The template is in
[checkpoints.md §3d](references/checkpoints.md#3d-the-task-card-ask-and-wait).
Ask about every `leak?`, `group-id?` and `date` column. A 0/1 or 1–5
integer target is ambiguous: ask whether it's a category or a quantity.
**Never prepare an unconfirmed task.**

**Prepare** exactly what the user confirmed:

```bash
ssh caml-vps camlctl caml prepare-data /home/caml/data/churn-anon.csv --target Churn --type binary --drop customer_id --drop refund_flag --metric auc --name churn --folds 5
```

| Option | Use |
|---|---|
| `--target COL` | The confirmed target, by name or number |
| `--type binary\|multiclass\|regression` | The confirmed task type. Always pass it |
| `--drop COL` (repeatable) | Leave out IDs, leaky and unwanted columns |
| `--keep COL` (repeatable) | Use only these features (not with `--drop`) |
| `--metric NAME` (repeatable) | The first ranks and is optimized: `auc`, `balacc`, `pr_auc`, `logloss`, `rmse`, `mae`, `r2`, ... |
| `--folds 5` (default; 10 for a benchmark study) | Stratified k-fold for classification, plain k-fold for regression |
| `--folds 1 --test-size 0.2` | One holdout split, for big data or a tight budget |
| `--name NAME` | The task name in results (default: the file name) |
| `--seed N` | A different split (default 42; record it) |
| `--force` | Overwrite an earlier preparation of the same name |

Column numbers are the ones `describe-data` prints. Read `prepare-data`'s
output back against the card, and save the card and the command as
`task.md` in the report folder. Rows that are **grouped** (several per
customer or patient) or **ordered in time** need the manual split in
[references/data-preparation.md](references/data-preparation.md) instead,
because random folds leak across them.

`prepare-data` writes `input/datasets/<name>/` in the repo: the fold CSVs,
`<name>.yaml` (the benchmark definition) and `dataset.json` (the source's
SHA-256, row counts, metrics and seed). From now on, pass
`--benchmark input/datasets/<name>/<name>.yaml`.

## Phase 5: Run and monitor the sweep

Choose the frameworks and the budget **by the goal** (Phase 0): for a
benchmark study, every framework that can run, under one constraint; for
the best model, screen everything with `quick`, then re-run the top 2–3
under `1h8c` with the same folds. The default list is everything installed,
minus the two special cases:

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

**Shape it by the goal.** A benchmark study gets the full report: methods
(the confirmed task card, setup, versions, seeds, hardware), the complete
leaderboard with spread, every failure, time against score, limitations and
citations. For the best model, keep it to one page: the winner, which
runners-up are within noise, the time and cost trade-off, and how to use
it. If the user wants the trained model, fit the winner on all the data on
the server with that framework's own Python
(`camlctl start final script --framework AutoGluon fit_final.py`) and bundle
it ([reporting.md](references/reporting.md#handing-over-the-winner-goal-b)).

[references/reporting.md](references/reporting.md) has both report
templates and explains how to read `results.csv`.

## Phase 8: Clean up

Ask before deleting anything. Tell the user what's left on the server (the
frameworks, their data in `~caml/data`, the prepared folds, the outputs) and
ask whether to delete their data there. Remind them to **delete the VPS** in
their provider's console; it bills while it exists. If they'll reuse it,
`camlctl update` updates the code later and keeps the installed frameworks.
If the server stays, ask whether to keep their keys there
(`camlctl secrets --remove --all` deletes them).

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
  version = {1.2.0},
  url     = {https://github.com/A1i-Tabatabaei/CAML},
  license = {Apache-2.0}
}
```

Plain text: Tabatabaei, A. (2026). *CAML: Benchmarking open-source AutoML
frameworks in isolated environments* (Version 1.2.0) [Computer software].
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
| Keys: what's set | `ssh caml-vps camlctl secrets --check` |
| Keys: the user enters them | `ssh -t caml-vps camlctl secrets` (in their own terminal) |
| Keys: from a filled-in file | `scp caml-secrets.env caml-vps:caml-secrets.env`, then `ssh caml-vps camlctl secrets --import caml-secrets.env` |
| Take in the data | `scp FILE caml-vps:NAME.csv`, then `ssh caml-vps camlctl dataset NAME.csv` |
| Probe it (no values printed) | `ssh caml-vps camlctl caml describe-data /home/caml/data/NAME.csv --target COL` |
| Remove identifiers | `ssh caml-vps camlctl caml anonymize-data /home/caml/data/NAME.csv --drop COL --hash COL --delete-original` |
| Prepare data (after the user confirms) | `ssh caml-vps camlctl caml prepare-data /home/caml/data/NAME.csv --target COL --type TYPE --name NAME` |
| Preview a sweep | `ssh caml-vps camlctl caml sweep FW... --benchmark YAML --constraint quick --dry-run` |
| Run a sweep (detached) | `ssh caml-vps camlctl start sweep caml sweep FW... --benchmark YAML --constraint quick` |
| Monitor | `ssh caml-vps camlctl status`, `ssh caml-vps camlctl wait sweep 540` |
| A job's log | `ssh caml-vps camlctl logs sweep 100` |
| Rank | `ssh caml-vps camlctl caml leaderboard --benchmark YAML --markdown` |
| Results to your machine | `ssh caml-vps camlctl bundle NAME`, then `scp caml-vps:caml-bundles/NAME.tar.gz .` |
| Compare across 2+ datasets | `ssh caml-vps camlctl caml compare FW1 FW2 ... --constraint quick` |
| Train the winner on all data | `ssh caml-vps camlctl start final script --framework FW fit_final.py` |
