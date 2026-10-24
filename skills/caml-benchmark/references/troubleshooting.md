# Troubleshooting a CAML benchmark

Start with the job's own log (`output/sweeps/<sweep>/logs/<fw>.<task>.<fold>.log`)
and the ledger's `detail` field. The repo's
`docs/operations/troubleshooting.md` holds every problem met so far, and
`docs/operations/known-issues.md` the open ones (cited below as KI-nn).

## Your machine and SSH

| Symptom | Cause | Fix |
|---|---|---|
| `ssh -o BatchMode=yes caml-vps echo ok` asks for a password, or says `Permission denied (publickey)` | No key login yet | The SSH section of your OS's operator profile; the user copies the key with the server password |
| `Bad configuration option: usekeychain` | A Mac's `~/.ssh/config` used on Linux or Windows | Remove `UseKeychain`, or add `IgnoreUnknown UseKeychain` as the first line |
| ssh on Windows ignores `~/.ssh/config`, or reports garbage in it | Written by Windows PowerShell 5.1's `>` or `Out-File` (UTF-16), or saved as `config.txt` | Recreate it with `Add-Content -Encoding ascii` ([operator-windows.md](operator-windows.md)) |
| `bash: $'\r': command not found` on the server | A script with Windows CRLF line endings | Run scripts with `camlctl script` (it strips CR). Repo clones keep LF through `.gitattributes`. |
| A remote command behaves differently from the docs | Your local shell expanded `$`, a backtick or `%` | Use `camlctl`, or one pair of double quotes without those characters |
| `camlctl: command not found` | Setup hasn't run yet, or it failed before installing camlctl | `ssh caml-vps bash /opt/caml-src/scripts/camlctl setup --detach` |
| `camlctl must run as root, or as a user with passwordless sudo` | Logged in as a user without passwordless sudo | Log in as root (`User root` in the alias), or ask the user to fix sudo |
| `camlctl wait` keeps exiting 124 | The job is still running | Keep waiting; `camlctl logs JOB` shows progress |
| A job shows `lost` | The server rebooted, or the job was SIGKILLed | Start it again with the same arguments; sweeps resume |

## Keys and the data

| Symptom | Cause | Fix |
|---|---|---|
| `camlctl secrets` says it needs a terminal | It ran through your shell tool, or without `-t` | The user runs `ssh -t caml-vps camlctl secrets` in their own terminal window, or uses the file route ([checkpoints.md](checkpoints.md) §2) |
| `secrets --check` says `missing` after the user typed a key | They pressed Enter without pasting, or pasted into the wrong window | Run it again. In Windows Terminal, paste with Ctrl+V or a right-click; nothing appears, which is expected |
| `secrets --import` exits 1 with `nothing imported` | The file was uploaded before the user saved it, or every value was left empty | Ask the user to fill in and save it, then upload and import it again. The uploaded copy is already deleted |
| `line N: not a NAME=value line` | A line without `=`, or a NAME not in capitals (for example a key pasted on its own line) | The user fixes that line (`TABPFN_TOKEN=...`). camlctl never echoes such lines |
| `Target column 'x' not found` or `--drop column '4 x' not found` | A name with spaces or symbols, split by the ssh command line | Pass the column's number from `describe-data` instead (`--drop 4`) |
| `Metric(s) ... don't apply to a binary task` | A metric for another task type (`rmse` for classification, `auc` for multiclass) | Use one from the list it prints; multiclass AUC is `auc_ovr` |

## Setup

| Symptom | Cause | Fix |
|---|---|---|
| `curl` to `www.openml.org` hangs or times out | The server's network can't reach OpenML, or OpenML is down (KI-07) | Try again later, or use another provider or region. The user's own data doesn't need OpenML, but the `test` smoke benchmark does. |
| `caml doctor` prints `MISSING` for an apt package | `bootstrap_vps.sh` didn't run, or failed | Re-run `camlctl setup --detach` (it's idempotent), and read `camlctl logs setup` |
| `caml: command not found` | Not using the project's environment | Go through `camlctl caml ...`, which runs `uv run caml` in the repo |
| `Incorrect benchmark name or path` | A typo in the YAML path | Paths are relative to the repo (`input/datasets/NAME/NAME.yaml`), or absolute |
| `X is not installed -- run caml install X first` | `caml sweep` checks every framework before it starts | `camlctl install X`, or drop X from the list |
| `camlctl install` ends with `failed: X` | One framework's dependencies failed to resolve or build | `camlctl install --force X` to retry, and read its error (`camlctl logs install 200`). Network errors are usually transient. |
| `TABPFN_TOKEN is not set (or is still the placeholder value)` | No key in the job's environment | `camlctl secrets --check`, then the user enters it ([checkpoints.md](checkpoints.md) §2). camlctl's loader is in `~/.profile`, not `~/.bashrc`. |
| `TabPFNLicenseError` | The TabPFN-3 model license wasn't accepted | The user accepts it on ux.priorlabs.ai (Licenses tab) |

## Jobs that fail

| Status / message | Cause | What to do |
|---|---|---|
| `killed` | Almost always the kernel's out-of-memory killer | `camlctl status` counts OOM kills since boot. Use a bigger server, `--folds 1`, or a row sample. Report it as a memory limit. |
| `timeout` | The framework overran its budget by far (the hard limit is 2 × budget + 20 min) | Report it; check the log tail for a hang |
| Local TabPFN: refuses more than 1,000 samples on CPU | TabPFN-3's CPU guard (KI-30) | Expected on CPU servers with more than about 1,000 training rows. Use a GPU server, or leave TabPFN out. |
| TPOT: `No individuals could be evaluated in the initial population` | TPOT's search finished nothing within the budget, or couldn't handle the data (KI-24) | A longer constraint. Otherwise report it. |
| GAMA: `IndexError: list index out of range` in `best_fit.py` | Wide data and a short budget: no pipeline was evaluated (KI-23) | A longer constraint. Otherwise report it. |
| FEDOT: `y contains previously unseen labels` | True/False target labels (KI-05) | Map the labels to words and re-prepare the data |
| SapientML: a `KeyError` at predict time | Its generated pipeline fails on some messy data (KI-22) | Upstream bug: report it |
| NaiveAutoML: `KeyError: nan` | Upstream bug on every task (KI-20) | Don't include NaiveAutoML |
| `crash` or `no_result` | CAML itself failed for that job | Read the log. If it isn't the data, open an issue with the log tail. |

## Sweeps

| Symptom | Cause | Fix |
|---|---|---|
| `another caml sweep is already running on ...` | A second driver started on the same sweep | `camlctl jobs` shows it. Wait, or (with the user's OK) `camlctl stop JOB`; the lock frees itself when the process exits. |
| The SSH session dropped and the sweep stopped | It ran in the foreground, not as a job | Start it with `camlctl start sweep caml sweep ...` and the same arguments. Finished jobs are skipped. |
| Scores look different from an earlier run | A different constraint, seed, server or framework version | Compare the `constraint`, `seed`, `version` and `app_version` columns |
| `leaderboard` shows old results mixed in | `results.csv` keeps everything, from every run | Filter with `--constraint` and `--task`. The leaderboard already keeps only the latest run of each job. |
| The server is too slow for the matrix | The matrix is too big | Fewer frameworks or folds, `--constraint quick`, or `--shard` across two servers |

## When to stop and ask the user

- A framework fails on every fold for a reason that isn't the data: ask
  whether to drop it or to try a longer budget.
- Memory kills on most frameworks: the server is too small for the data.
  Ask about a bigger server or sampling.
- Anything that would cost more (a larger server, more hours) or upload
  the data anywhere new.
