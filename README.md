<p align="center">
  <img src="docs/assets/banner.svg" width="100%"
       alt="CAML: an open-source AutoML benchmark. Benchmark every major AutoML framework on your own data. A terminal shows caml prepare-data, caml install --all, caml sweep and caml leaderboard; chips list AutoGluon, H2O AutoML, LightAutoML, MLJAR, FLAML, TPOT, GAMA, FEDOT, TabPFN, TabPFN Client and SapientML.">
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-4B54C6"></a>
  <a href="#frameworks"><img alt="11 framework integrations verified" src="https://img.shields.io/badge/frameworks-11%20verified-7A3CE0"></a>
  <a href="pyproject.toml"><img alt="Python 3.11 | 3.12" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-0E9E6B"></a>
  <a href="#run-it-on-a-vps"><img alt="Ubuntu 24.04" src="https://img.shields.io/badge/runs%20on-Ubuntu%2024.04-C9740A"></a>
  <a href="#for-ai-agents"><img alt="Driven from Windows, macOS or Linux" src="https://img.shields.io/badge/driven%20from-Windows%20%7C%20macOS%20%7C%20Linux-2F6FDE"></a>
  <a href="https://github.com/astral-sh/uv"><img alt="Environments by uv" src="https://img.shields.io/badge/envs-uv-D23F72"></a>
  <a href="https://github.com/A1i-Tabatabaei/CAML/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/A1i-Tabatabaei/CAML/actions/workflows/ci.yml/badge.svg"></a>
</p>

<p align="center">
  <a href="#quick-start"><b>Quick start</b></a> &nbsp;·&nbsp;
  <a href="#benchmark-your-own-data"><b>Your data</b></a> &nbsp;·&nbsp;
  <a href="#frameworks"><b>Frameworks</b></a> &nbsp;·&nbsp;
  <a href="#for-ai-agents"><b>AI agents</b></a> &nbsp;·&nbsp;
  <a href="docs/"><b>Docs</b></a> &nbsp;·&nbsp;
  <a href="#citing-caml"><b>Cite</b></a>
</p>

---

**CAML benchmarks the major open-source AutoML frameworks on any tabular
dataset, yours or the OpenML suites, behind one command line.** Each
framework is installed at a pinned, current version into its own isolated
[`uv`](https://github.com/astral-sh/uv) environment, so a framework that needs
`numpy<2` runs next to one that needs `numpy 2.x`. CAML then trains,
predicts, scores and ranks them the same way, and it records every failure
instead of dropping it.

It is a from-scratch rewrite inspired by OpenML's
[AutoML Benchmark](https://github.com/openml/automlbenchmark) (AMLB). CAML
keeps AMLB's core design: one sandbox per framework, with data crossing a
subprocess boundary. It replaces the install layer (stale pins, `deadsnakes`,
Docker) that keeps AMLB from installing on a current Ubuntu box.

<table>
<tr>
<td width="33%" valign="top">

**Every framework, one CLI**<br>
Install, run, sweep and compare 11 framework integrations with the same
commands and the same scoring.

</td>
<td width="33%" valign="top">

**Isolation that installs**<br>
One `uv` venv per framework, each with its own Python and exact pins. No
Docker, no PPAs, no dependency fights.

</td>
<td width="33%" valign="top">

**Your data in one command**<br>
`caml prepare-data` turns a CSV or Parquet file into stratified folds with
an explicit task type.

</td>
</tr>
<tr>
<td valign="top">

**Sweeps that survive**<br>
One isolated job per framework × task × fold. Resumable, shardable across
boxes, and every failure is classified.

</td>
<td valign="top">

**Honest statistics**<br>
A per-dataset leaderboard, and Wilcoxon / Friedman + Holm tests across
datasets, paired per task and never per fold.

</td>
<td valign="top">

**Ready for AI agents**<br>
Copy-paste prompts for Windows, macOS and Linux, a bundled <a href="skills/caml-benchmark/SKILL.md">agent skill</a>, and one quote-free server command, <code>camlctl</code>.

</td>
</tr>
</table>

## Quick start

CAML runs on an Ubuntu 24.04 server. Framework installs are large (AutoGluon
alone pulls about 170 packages), so use a VPS, not your laptop. Your own
machine only sends commands, and the same commands work from **Windows
(PowerShell or Git Bash), macOS and Linux**:

```bash
ssh root@<your-server> "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
ssh root@<your-server> bash /opt/caml-src/scripts/camlctl setup
ssh root@<your-server> camlctl install FLAML
ssh root@<your-server> camlctl caml run FLAML --benchmark test --constraint test
ssh root@<your-server> camlctl caml leaderboard --benchmark test
```

`camlctl setup` installs the apt baseline, uv, an unprivileged `caml` user
and the workspace, and ends with `caml doctor`. `camlctl install FLAML` puts
one framework in its own venv. The `test` benchmark is 3 small OpenML tasks
× 2 folds. `camlctl` is the one server command
([reference](skills/caml-benchmark/references/camlctl.md)): it runs `caml` as
the `caml` user, detaches long jobs (`camlctl start`), and reports progress
(`camlctl status`). `camlctl install --all` installs the whole roster.
[Run it on a VPS](#run-it-on-a-vps) covers sizing and the other routes. To
hand the whole job to an AI agent, copy a prompt from
[For AI agents](#for-ai-agents).

## Benchmark your own data

<p align="center">
  <img src="docs/assets/workflow.svg" width="100%"
       alt="Workflow: your data (one CSV, TSV or Parquet file plus the target column) is copied to your Ubuntu VPS with scp. There, caml prepare-data writes stratified folds and checks the task type, caml install --all builds one uv venv per framework, caml sweep runs one job per framework and fold (resumable, failures kept), and caml leaderboard ranks frameworks by mean score with Markdown output for reports.">
</p>

From your machine, with `<host>` your server (or an SSH alias for it):

```bash
scp churn.csv root@<host>:churn.csv
ssh root@<host> camlctl dataset churn.csv
ssh root@<host> camlctl caml describe-data /home/caml/data/churn.csv --target churned
ssh root@<host> camlctl caml prepare-data /home/caml/data/churn.csv --target churned --type binary --drop customer_id
ssh root@<host> camlctl start install install AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML
ssh root@<host> camlctl start sweep caml sweep AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML --benchmark input/datasets/churn/churn.yaml --constraint quick
ssh root@<host> camlctl status
ssh root@<host> camlctl caml leaderboard --benchmark input/datasets/churn/churn.yaml
```

- **`camlctl dataset`** moves the upload into `~caml/data`, prints its SHA-256,
  encoding, separator, columns and rows, and offers the fix for a non-UTF-8
  Excel export (`--from-encoding WINDOWS-1252`).
- **`describe-data`** shows each column's kind, missing share, distinct count
  and flags (row ID, possible personal data, possible leak, dates, grouped
  rows), the task type the target implies and what to check, without printing
  the data's values. `anonymize-data` drops identifying columns or replaces
  IDs with irreversible pseudonyms.
- **`camlctl start`** runs the installs and the sweep as detached jobs that
  survive your SSH session; wait for the install job to finish before you
  start the sweep (`camlctl wait install 540`).

- **`prepare-data`** reads CSV, TSV or Parquet. It writes 5 stratified folds
  by default (`--folds 1` gives a single holdout), drops rows with a missing
  target, and refuses classes too rare to appear in every fold. `--drop` or
  `--keep` choose the features and `--metric` the ranking metric; columns
  go by name or by number. It always
  writes the task type explicitly: a 0/1 integer target is a classification
  problem, and without the explicit type CAML's loader would treat it as
  regression. It prints why it chose the type, so you can override it with
  `--type`.
- **`sweep`** runs each (framework, fold) as its own job. Re-running the same
  command resumes, and `--shard 1/2` / `--shard 2/2` split the matrix across
  two servers. Run it detached (`camlctl start`); see [docs/operations/sweeps.md](docs/operations/sweeps.md).
- **`quick`** gives each job 5 minutes on every core, which is right for a first
  screening. Re-run your top frameworks under `1h8c` before relying on the
  ranking. Wall-clock is about frameworks × folds × (budget + a few minutes).
- **`leaderboard`** ranks frameworks by mean score across folds and shows
  the spread, the folds that succeeded and the training time.
  `--markdown` prints a table ready for a report.

Real output, from CAML's own smoke-test history (OpenML task kc2,
2 folds, 60-second budget):

```text
kc2  (binary, constraint test, metric auc: higher is better)
rank  framework        auc mean  std     folds ok  train s (mean)
----  ---------------  --------  ------  --------  --------------
1     FLAML            0.9010    0.0360  2/2       60
2     MLJARSupervised  0.8880    0.0436  2/2       63
```

> [!IMPORTANT]
> **TabPFN and your data.** Local `TabPFN` runs fully on your server, but its
> weights need a free Prior Labs token, and on CPU it refuses more than 1,000
> training rows. `TabPFNClient` **uploads your data to Prior Labs' servers**,
> so leave it out of a sweep unless you are allowed to share the data. See
> [TabPFN setup](#tabpfn-setup).

## Frameworks

All 11 integrations solve tabular binary classification, multiclass
classification and regression.

<p align="center">
  <img src="docs/assets/families.svg" width="88%"
       alt="The roster grouped by technique: gradient-boosting ensembles (AutoGluon, H2O AutoML, LightAutoML, MLJAR-supervised); cost-frugal search (FLAML); evolutionary / genetic (TPOT, GAMA, FEDOT); foundation model (TabPFN local, TabPFNClient hosted); code synthesis (SapientML).">
</p>

| Framework | CAML name | Approach | Pinned | License |
|---|---|---|---|---|
| [AutoGluon](docs/frameworks/autogluon.md) | `AutoGluon` | Multi-layer stacked ensembles; usually near the top of AMLB | 1.5.0 | Apache-2.0 |
| [H2O AutoML](docs/frameworks/h2o.md) | `H2OAutoML` | GBM/GLM/deep-learning models plus a stacked ensemble, on a JVM | 3.46.0.11 | Apache-2.0 |
| [LightAutoML](docs/frameworks/lightautoml.md) | `LightAutoML` | Gradient boosting and linear models, blended | 0.4.2 | Apache-2.0 |
| [MLJAR-supervised](docs/frameworks/mljarsupervised.md) | `MLJARSupervised` | Ensembles with automatic explanations and reports | 1.3.1 | MIT |
| [FLAML](docs/frameworks/flaml.md) | `FLAML` | Microsoft's fast, cost-frugal hyperparameter search | 2.6.0 | MIT |
| [TPOT](docs/frameworks/tpot.md) | `TPOT` | Genetic programming over scikit-learn pipelines | 1.1.0 | LGPL-3.0 |
| [GAMA](docs/frameworks/gama.md) | `GAMA` | Evolutionary search over pipelines | 23.0.0.post1 | Apache-2.0 |
| [FEDOT](docs/frameworks/fedot.md) | `FEDOT` | Evolutionary optimization of pipeline graphs | 0.7.5 | BSD-3-Clause |
| [TabPFN](docs/frameworks/tabpfn.md) | `TabPFN` | A pretrained transformer that predicts in one forward pass, on your server | 8.1.0 | Apache-2.0 code; non-commercial weights |
| [TabPFN client](docs/frameworks/tabpfn-client.md) | `TabPFNClient` | The same model through Prior Labs' hosted API (data leaves the server) | 0.3.3 | Apache-2.0 |
| [SapientML](docs/frameworks/sapientml.md) | `SapientML` | Generates pipeline source code from a corpus of human pipelines | 0.4.17 | Apache-2.0 |
| [NaiveAutoML](docs/frameworks/naiveautoml.md) | `NaiveAutoML` | *Skipped: a confirmed upstream bug fails every task* | 0.1.6 | MIT |

<details>
<summary><b>Which one should I try first?</b></summary>

| If you want… | Try | Why |
|---|---|---|
| The strongest general-purpose scores | AutoGluon | Deep stacked ensembles |
| A fast result from a small install | FLAML | Smallest dependency tree, quick search |
| Instant predictions on a small dataset, kept private | TabPFN | No search: one forward pass, on your server |
| Model explanations alongside the model | MLJAR-supervised | Writes explanation reports |
| A robust JVM workhorse | H2O AutoML | Battle-tested stacked ensembles |
| To compare evolutionary approaches | TPOT, GAMA, FEDOT | Three takes on pipeline search |
| Inspectable pipeline code | SapientML | Writes out the pipeline it built |

Or run them all: that's what CAML is for. On deliberately messy data
(missing values, odd label types), AutoGluon, FLAML, GAMA, H2O AutoML,
LightAutoML, MLJAR and TabPFNClient passed all 9 stress-test datasets. FEDOT,
SapientML and TPOT each failed on specific edge cases
([details](docs/operations/e2e-verification.md)).

</details>

Each framework's manifest (`frameworks/<Name>/framework.toml`) declares its
pin, Python range and system packages. Versions are exact-pinned and bumped
on purpose: `caml check-versions` lists newer releases, and
`caml install <name> --latest` is a one-off escape hatch.

## How it works

<p align="center">
  <img src="docs/assets/pipeline.svg" width="100%"
       alt="caml run loads a dataset (an OpenML task or local CSV); the framework's fit and predict run inside an isolated uv venv, receiving X, y and the config as JSON over stdin and returning predictions as JSON; the orchestrator scores them against the ground truth (AUC, log loss, RMSE) into results.csv.">
</p>

The orchestrator owns data loading and scoring. A framework only ever sees a
train/test split and a config, and only hands back predictions, so every
framework is scored by the same code. The framework runs in its own venv, as
a subprocess:

<p align="center">
  <img src="docs/assets/isolation.svg" width="94%"
       alt="One caml orchestrator (its own uv env, Python 3.12: CLI, dataset loader, scoring) above a subprocess boundary; below it each framework runs in its own isolated uv venv with its own Python and dependencies, talking to the orchestrator only through JSON over stdin and stdout.">
</p>

| | AMLB | CAML |
|---|---|---|
| Environments | stdlib `venv` + `pip`, Python from the `deadsnakes` PPA | `uv` for interpreters, venvs and installs |
| Framework setup | A hand-written `setup.sh` each, plus one large `frameworks.yaml` | One declarative `framework.toml` each, one shared installer |
| Versions | `"stable"` = `pip install -U` at install time | Exact pins, bumped on purpose |
| Runners | Docker, Singularity, AWS | One Ubuntu server, bare-metal venvs |

Design notes are in [docs/architecture/](docs/architecture/overview.md), and
the file-by-file provenance of the code adapted from AMLB is in
[NOTICE.md](NOTICE.md).

## Run it on a VPS

| | Minimum (smoke tests) | Recommended (full-roster sweeps) |
|---|---|---|
| CPU | 4 vCPU | 8 dedicated vCPU (x86_64) |
| RAM | 8 GB (a 4 GB swapfile is added below 8 GB) | 32 GB |
| Disk | 50 GB | 150–200 GB SSD |
| OS | Ubuntu 24.04, root or sudo over SSH | same; no GPU needed |

**From any machine** (Windows, macOS or Linux): clone onto the server and
let `camlctl` set it up. `--detach` runs it as a job that survives a dropped
connection, and `wait` blocks until it's done (repeat it while it exits 124):

```bash
ssh root@<host> "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
ssh root@<host> bash /opt/caml-src/scripts/camlctl setup --detach
ssh root@<host> camlctl wait setup 540
```

`camlctl update` pulls later versions and keeps the venvs and results.

**From a clone, for developers** (Linux, macOS, or Git Bash/WSL on Windows):
`provision_vps.sh` packages your checkout with `git archive`, pushes it over
SSH, and needs no credentials on the server. `sync_vps.sh` pushes later code
changes and keeps the venvs and results.

```bash
scripts/provision_vps.sh root@<host>
scripts/sync_vps.sh root@<host>
```

<p align="center">
  <img src="docs/assets/provisioning.svg" width="100%"
       alt="provision_vps.sh root@host packages HEAD with git archive and pushes it over SSH (no credentials on the box), runs bootstrap_vps.sh as root (apt baseline, uv, caml user, swap), then setup_workspace.sh as the caml user (workspace layout, uv sync), ending at a green caml doctor.">
</p>

<details>
<summary><b>Manual setup on the server instead</b></summary>

```bash
# as root
git clone https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src
bash /opt/caml-src/scripts/bootstrap_vps.sh          # apt baseline, uv, the caml user, swap, camlctl
sudo -iu caml bash /opt/caml-src/scripts/setup_workspace.sh   # clones into ~/caml-workspace, uv sync, caml doctor
```

</details>

Before anything else on a new server, run `camlctl info`: it checks the OS,
RAM, disk, and whether PyPI, GitHub, the PyTorch index and OpenML answer
(every OpenML benchmark downloads its data from there; your own data
doesn't need it). Run long jobs detached, so they survive your SSH session:
`camlctl start sweep caml sweep ...`, then `camlctl status`. When you're
done, `camlctl bundle` packs the results for `scp`. Copy them off and delete
the server; you're billed while it exists. More in [the VPS runbook](docs/operations/vps-runbook.md)
and [GPU support](docs/operations/gpu.md) (CAML detects a GPU and uses it
for TabPFN, AutoGluon and LightAutoML).

## TabPFN setup

Both TabPFN variants need a free Prior Labs API key in `TABPFN_TOKEN`:

1. Register at [ux.priorlabs.ai](https://ux.priorlabs.ai), accept the
   licenses on the Licenses tab (the TabPFN-3 model license is required by the
   local `TabPFN`), and copy an API key.
2. Store it on the server for the `caml` user. Run this yourself, in your
   own terminal. It asks for each key without showing it, so the key never
   reaches your shell history, the repo or an agent's chat:

   ```bash
   ssh -t root@<host> camlctl secrets
   ```

   It writes the keys to `~caml/.caml-secrets` (mode 600), which camlctl
   loads for every command it runs as `caml`. `camlctl secrets --check` prints `set` or
   `missing` for each key, never the key. To use a file instead,
   `camlctl secrets --template` prints one to fill in, and
   `camlctl secrets --import FILE` stores the keys from it and deletes it.
3. `camlctl install TabPFN` (local) and/or `camlctl install TabPFNClient` (hosted).

| | `TabPFN` (local) | `TabPFNClient` (hosted) |
|---|---|---|
| Where it runs | On your server, CPU or GPU | Prior Labs' servers |
| Does your data leave the server? | No (the token only authorizes a one-time weight download) | **Yes, on every fit and predict** |
| Size limits | CPU: at most 1,000 training rows. A GPU lifts that. | Server-side limits and daily quotas |
| License | Code Apache-2.0; **weights non-commercial** | Apache-2.0 client; Prior Labs' terms of service |

Never commit the token. [docs/operations/tabpfn-access.md](docs/operations/tabpfn-access.md) has the details.

## Benchmarks, constraints and results

A **benchmark** chooses the datasets; a **constraint** chooses the budget per job.

| Benchmark | What |
|---|---|
| `test` | 3 small OpenML tasks (binary, multiclass, regression): "does it install and score?" |
| `validation` | 9 deliberately messy OpenML datasets: "is it robust?" |
| `pilot` | 9 tasks from the official AMLB suites, each chosen to exercise one risk |
| `openml/s/271`, `openml/s/269` | The full AMLB suites: 71 classification and 33 regression tasks |
| any `.yaml` path | Your own data, written by `caml prepare-data` |

| Constraint | Folds | Budget per job | Cores |
|---|---|---|---|
| `test` | 2 | 600 s (the `test` benchmark sets 60 s) | 4 |
| `quick` | 3 | 300 s | all |
| `pilot` | 2 | 600 s | 4 |
| `1h4c` / `1h8c` | 10 | 1 hour | 4 / 8 |
| `4h8c` / `8h8c` | 10 | 4 / 8 hours | 8 |

A task's own `folds:` wins over the constraint's. Every job appends one row to
`output/results.csv`: the score (`result`, normalized so higher is better),
every metric (AUC, log loss, accuracy and balanced accuracy for
classification; RMSE, R² and MAE for regression), durations, framework
version, seed, the CAML revision (`app_version`), which input columns the
final model used, and, for a failed job, the error in `info`.

- `caml leaderboard` ranks frameworks per dataset.
- `caml compare FW1 FW2 [FW3...]` tests significance **across datasets**. It
  needs at least 2 tasks: a Wilcoxon signed-rank test for two frameworks, a
  Friedman test with Holm-corrected pairwise tests for three or more,
  following Demšar (2006).
- `caml sweep` adds a ledger (`output/sweeps/<name>/ledger.jsonl`) that
  classifies every failure as `error`, `timeout`, `killed`, `crash` or
  `no_result`.

## For AI agents

### Hand the whole job to an agent

Copy the prompt for your operating system, fill in **My details**, and paste
it into your agent: Claude Code, Codex, Cursor, Copilot, or any agent that
can run commands on your computer. The agent:

- confirms which OS and shell it's in, and reads the matching instructions
  from this repo;
- asks your **goal**: a benchmark study you'll write about, or the best
  model for your project. The answer shapes the plan and the report;
- sets up your Ubuntu server over SSH, and has **you** type in any API key
  (TabPFN's), in your own terminal and never in the chat;
- looks at your data's structure without reading its values, removes
  personal data if you ask, and has you **confirm the task**: what to
  predict, binary, multiclass or regression, which columns to use, and how
  rows relate;
- benchmarks your data, monitors the run, and writes an honest report.

CAML always runs on the Ubuntu server; your computer only sends commands.

You need an Ubuntu 24.04 server with root SSH (the IP and root password
from your provider), your dataset as CSV or Parquet, and the column to
predict. The agent can walk you through SSH key setup, or you can do it
first: [the 10-minute setup](docs/getting-started/agent-prompt.md).

<details>
<summary><b>Windows: PowerShell, Git Bash or WSL</b></summary>

<!-- prompt:windows -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on Windows, and you have a shell on this PC. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This PC only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. C:\Users\me\Downloads\churn.csv>
- Goal: <benchmark study: the comparison itself goes into my article, thesis or report | best model: I'll use the winner in the rest of my project | both | not sure>
- What I want to predict: <column and what it means | not sure: suggest one>
- Personal data in the file: <none | yes, already anonymized | yes, not anonymized yet>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip | local TabPFN, non-commercial use | also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. C:\caml-run>

How to work:
1. Find out which shell you're in (PowerShell, Git Bash, cmd or WSL; operator-windows.md shows how), and confirm this is Windows. If it isn't, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-windows.md (this PC: commands and gotchas), references/checkpoints.md (the three check-ins with me), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Stop and wait for my answer at each of the three check-ins in checkpoints.md:
   a. Goal: in your first message, confirm my goal (ask it if I left it blank), and send your plan in under 10 lines (frameworks, folds, constraint, estimated duration, which keys you'll need), shaped by the goal, with your questions. Wait for my OK before you change anything on the server.
   b. Credentials: after setup, run `camlctl secrets --check`. If the plan needs a key that isn't set (TabPFN needs TABPFN_TOKEN), ask me to run `ssh -t caml-vps camlctl secrets` in my own terminal, where it hides what I type. If I'd rather use a file, create caml-secrets.env in my report folder from `camlctl secrets --template`, let me fill it in, then upload it, import it with `camlctl secrets --import`, and delete it. Never open, read or print that file once I've filled it in.
   c. Task: after uploading my data, and removing personal data first if it isn't anonymized (agree the columns with me), probe it with `camlctl caml describe-data`, which never prints values. Then show me the task card: what to predict (y), the task type (binary, multiclass or regression), the feature columns (X) with each one you'd leave out and why, whether all the other features should be used, how rows relate (independent, grouped or ordered in time), and the metric. Prepare the data only after I confirm it.

Rules:
- Never ask me for, or handle, passwords, private keys or API keys (the TabPFN key included). When one is needed, give me the command to run myself, or the file to fill in.
- My data goes to my server and nowhere else, and its values stay out of this chat: use describe-data, not head or cat.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-windows.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this PC and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on Windows.

Done means: every planned job is ok or its failure is explained; task.md (the confirmed task card), report.md (shaped by my goal, following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-windows.md are in my report folder, plus the trained model if I asked for one; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:windows -->

</details>

<details>
<summary><b>macOS</b></summary>

<!-- prompt:macos -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on macOS, and you have a shell on this Mac. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This Mac only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. /Users/me/Downloads/churn.csv>
- Goal: <benchmark study: the comparison itself goes into my article, thesis or report | best model: I'll use the winner in the rest of my project | both | not sure>
- What I want to predict: <column and what it means | not sure: suggest one>
- Personal data in the file: <none | yes, already anonymized | yes, not anonymized yet>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip | local TabPFN, non-commercial use | also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. ~/caml-run>

How to work:
1. Confirm this is macOS (`uname -s` prints Darwin) and note the shell. If it isn't, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-macos.md (this Mac: commands and gotchas), references/checkpoints.md (the three check-ins with me), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Stop and wait for my answer at each of the three check-ins in checkpoints.md:
   a. Goal: in your first message, confirm my goal (ask it if I left it blank), and send your plan in under 10 lines (frameworks, folds, constraint, estimated duration, which keys you'll need), shaped by the goal, with your questions. Wait for my OK before you change anything on the server.
   b. Credentials: after setup, run `camlctl secrets --check`. If the plan needs a key that isn't set (TabPFN needs TABPFN_TOKEN), ask me to run `ssh -t caml-vps camlctl secrets` in my own terminal, where it hides what I type. If I'd rather use a file, create caml-secrets.env in my report folder from `camlctl secrets --template`, let me fill it in, then upload it, import it with `camlctl secrets --import`, and delete it. Never open, read or print that file once I've filled it in.
   c. Task: after uploading my data, and removing personal data first if it isn't anonymized (agree the columns with me), probe it with `camlctl caml describe-data`, which never prints values. Then show me the task card: what to predict (y), the task type (binary, multiclass or regression), the feature columns (X) with each one you'd leave out and why, whether all the other features should be used, how rows relate (independent, grouped or ordered in time), and the metric. Prepare the data only after I confirm it.

Rules:
- Never ask me for, or handle, passwords, private keys or API keys (the TabPFN key included). When one is needed, give me the command to run myself, or the file to fill in.
- My data goes to my server and nowhere else, and its values stay out of this chat: use describe-data, not head or cat.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-macos.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this Mac and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on macOS.

Done means: every planned job is ok or its failure is explained; task.md (the confirmed task card), report.md (shaped by my goal, following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-macos.md are in my report folder, plus the trained model if I asked for one; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:macos -->

</details>

<details>
<summary><b>Linux</b></summary>

<!-- prompt:linux -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on Linux, and you have a shell on this machine. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This machine only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. /home/me/data/churn.csv>
- Goal: <benchmark study: the comparison itself goes into my article, thesis or report | best model: I'll use the winner in the rest of my project | both | not sure>
- What I want to predict: <column and what it means | not sure: suggest one>
- Personal data in the file: <none | yes, already anonymized | yes, not anonymized yet>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip | local TabPFN, non-commercial use | also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. ~/caml-run>

How to work:
1. Confirm this is Linux (`uname -s`), and whether it's WSL. If it isn't Linux, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-linux.md (this machine: commands and gotchas), references/checkpoints.md (the three check-ins with me), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Stop and wait for my answer at each of the three check-ins in checkpoints.md:
   a. Goal: in your first message, confirm my goal (ask it if I left it blank), and send your plan in under 10 lines (frameworks, folds, constraint, estimated duration, which keys you'll need), shaped by the goal, with your questions. Wait for my OK before you change anything on the server.
   b. Credentials: after setup, run `camlctl secrets --check`. If the plan needs a key that isn't set (TabPFN needs TABPFN_TOKEN), ask me to run `ssh -t caml-vps camlctl secrets` in my own terminal, where it hides what I type. If I'd rather use a file, create caml-secrets.env in my report folder from `camlctl secrets --template`, let me fill it in, then upload it, import it with `camlctl secrets --import`, and delete it. Never open, read or print that file once I've filled it in.
   c. Task: after uploading my data, and removing personal data first if it isn't anonymized (agree the columns with me), probe it with `camlctl caml describe-data`, which never prints values. Then show me the task card: what to predict (y), the task type (binary, multiclass or regression), the feature columns (X) with each one you'd leave out and why, whether all the other features should be used, how rows relate (independent, grouped or ordered in time), and the metric. Prepare the data only after I confirm it.

Rules:
- Never ask me for, or handle, passwords, private keys or API keys (the TabPFN key included). When one is needed, give me the command to run myself, or the file to fill in.
- My data goes to my server and nowhere else, and its values stay out of this chat: use describe-data, not head or cat.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-linux.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this machine and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on Linux.

Done means: every planned job is ok or its failure is explained; task.md (the confirmed task card), report.md (shaped by my goal, following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-linux.md are in my report folder, plus the trained model if I asked for one; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:linux -->

</details>

Every prompt also has the agent keep a **field report**
(`caml-field-report-<os>.md`). It records every error, workaround and
gotcha the agent hit, and what worked first time. Please send it back by
opening a [field report issue](https://github.com/A1i-Tabatabaei/CAML/issues/new/choose).
That's how CAML gets better on your OS.

### The agent skill

[`skills/caml-benchmark/`](skills/caml-benchmark/SKILL.md) is an
[Agent Skill](https://agentskills.io): the runbook those prompts point to.
It covers the operator machine (profiles for
[Windows](skills/caml-benchmark/references/operator-windows.md),
[macOS](skills/caml-benchmark/references/operator-macos.md) and
[Linux](skills/caml-benchmark/references/operator-linux.md)), the server
command [`camlctl`](skills/caml-benchmark/references/camlctl.md),
provisioning, data preparation, privacy (TabPFNClient), running, monitoring,
reporting, cleanup and the field report.

```text
/plugin marketplace add A1i-Tabatabaei/CAML
/plugin install caml@caml
```

That installs it in Claude Code. For other agents, copy `skills/caml-benchmark/`
into your agent's skills directory. Agents working inside this repo should
also read [AGENTS.md](AGENTS.md).

## Command reference

| Command | What it does |
|---|---|
| `caml doctor` | Checks uv, system packages, disk, swap, stray H2O JVMs and the GPU |
| `caml install <name>` / `--all` | Installs one framework, or all of them, into isolated venvs (`--force`, `--latest`) |
| `caml status` | Shows each framework's pin, installed version, Python and compute mode |
| `caml describe-data <file> [--target <col>]` | Describes each column (kind, missing, distinct, flags for IDs, personal data, leaks, dates) and the task, without printing values |
| `caml anonymize-data <file> --drop <col> --hash <col>` | Drops identifying columns, or replaces IDs with irreversible pseudonyms |
| `caml prepare-data <file> --target <col>` | Turns your CSV/TSV/Parquet file into folds and a benchmark YAML (`--type`, `--drop`/`--keep`, `--metric`) |
| `caml run <name> --benchmark B --constraint C` | Runs one framework (`--task`, `--fold`, `--seed`, `--keep-going`) |
| `caml sweep <names...> --benchmark B --constraint C` | Runs frameworks × tasks × folds as isolated, resumable jobs (`--shard`, `--dry-run`, `--retry-failed`) |
| `caml leaderboard [--benchmark B]` | Ranks frameworks per dataset (`--markdown`) |
| `caml compare <names...>` | Significance tests across datasets |
| `caml check-versions` | Lists pins that have a newer PyPI release |
| `caml uninstall <name>` | Removes a framework's venv |

Every flag, with examples: [docs/reference/cli.md](docs/reference/cli.md).

From your own machine, these run through `camlctl` on the server
(`ssh <host> camlctl caml <command> ...`). `camlctl`'s own commands are:

| `camlctl` command | What it does |
|---|---|
| `info` | Server facts and network checks, with warnings |
| `setup [--detach]` | Installs CAML on a fresh Ubuntu 24.04 server; idempotent |
| `caml ARGS...` | Runs `uv run caml ARGS...` as the `caml` user, in the repo |
| `install FW...` | Installs several frameworks, keeping going past failures |
| `dataset FILE` | Takes in an uploaded data file and describes it; converts non-UTF-8 exports |
| `script [--framework FW] FILE` | Runs an uploaded bash or Python script as `caml` (CRLF-safe), optionally with a framework's own Python |
| `start JOB ...`, `jobs`, `logs`, `wait`, `stop` | Detached jobs that survive SSH drops |
| `status` | Load, memory, disk, OOM kills, jobs and sweep progress on one screen |
| `bundle` | Packs results, prepared datasets and logs into one `.tar.gz` for `scp` |
| `secrets` | The user types API keys in (input hidden), or imports a filled-in file; `--check` never prints them |
| `update`, `version` | Updates the code; shows versions |

The full reference: [camlctl.md](skills/caml-benchmark/references/camlctl.md).

## Project status

CAML 1.0 covers tabular classification and regression. All 11 integrations
have been verified end to end on real servers; NaiveAutoML is skipped because
of an upstream bug. Open issues, unverified fixes and upstream limitations
live in one register,
[docs/operations/known-issues.md](docs/operations/known-issues.md). Two of
them matter when you plan a run:

- The **GPU code path** has unit tests, but no full GPU run has been
  verified yet.
- **`prepare-data`, `leaderboard` and the local-file dataset path** are new in
  1.0. They are tested end to end through the real orchestrator with a
  scikit-learn stand-in framework. Their first sweep with the real
  frameworks is still to come.

Time series, images, text and multimodal data are out of scope for now.

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started/install-orchestrator.md) | Installing the orchestrator, [bootstrapping a VPS](docs/getting-started/vps-bootstrap.md) |
| [Frameworks](docs/frameworks/) | One page per framework, with its real install and runtime gotchas |
| [Operations](docs/operations/) | [Sweeps](docs/operations/sweeps.md), [troubleshooting](docs/operations/troubleshooting.md), [known issues](docs/operations/known-issues.md), [GPU](docs/operations/gpu.md) |
| [Architecture](docs/architecture/overview.md) | [The framework plugin contract](docs/architecture/framework-plugin-contract.md), [version pinning](docs/architecture/version-pinning-policy.md) |
| [Contributing](CONTRIBUTING.md) | [Adding a framework](docs/contributing/adding-a-framework.md) |
| Project history | [STATUS.md](STATUS.md) (live state) and [CLAUDE.md](CLAUDE.md) (the full decision log) |

## Citing CAML

If CAML helps your research, please cite it. GitHub's **"Cite this
repository"** button uses [CITATION.cff](CITATION.cff).

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

Please also cite the AutoML frameworks you report on, and AMLB:
Gijsbers et al., *AMLB: an AutoML Benchmark*, JMLR 25(101), 2024.

## License and acknowledgments

CAML is released under the [Apache License 2.0](LICENSE). Parts of it are
adapted from the [OpenML AutoML Benchmark](https://github.com/openml/automlbenchmark)
(MIT, © 2018 OpenML); see [NOTICE](NOTICE) and [NOTICE.md](NOTICE.md). Each
AutoML framework keeps its own license and is installed from PyPI, never
redistributed here. Datasets come from [OpenML](https://www.openml.org) under
their own terms.

CAML stands for "Claude AML": it was built with
[Claude Code](https://claude.com/claude-code). It is an independent project,
not affiliated with or endorsed by Anthropic, OpenML or any of the framework
authors.
