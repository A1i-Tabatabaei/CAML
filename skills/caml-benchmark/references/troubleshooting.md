# Troubleshooting a CAML benchmark

Start with the job's own log (`output/sweeps/<sweep>/logs/<fw>.<task>.<fold>.log`)
and the ledger's `detail` field. The repo's
`docs/operations/troubleshooting.md` holds every problem met so far, and
`docs/operations/known-issues.md` the open ones (cited below as KI-nn).

## Setup

| Symptom | Cause | Fix |
|---|---|---|
| `curl` to `www.openml.org` hangs or times out | The server's network can't reach OpenML, or OpenML is down (KI-07) | Try again later, or use another provider or region. The user's own data doesn't need OpenML, but the `test` smoke benchmark does. |
| `caml doctor` prints `MISSING` for an apt package | `bootstrap_vps.sh` didn't run, or failed | Re-run `scripts/provision_vps.sh root@HOST` (it's idempotent) |
| `caml: command not found` | Not using the project's environment | Always `uv run caml ...` from `~/caml-workspace/CAML` |
| `Incorrect benchmark name or path` | Wrong working directory, or a typo in the YAML path | `cd ~/caml-workspace/CAML`; pass the YAML's full path |
| `X is not installed -- run caml install X first` | `caml sweep` checks every framework before it starts | `uv run caml install X`, or drop X from the list |
| `caml install --all` lists failures at the end | One framework's dependencies failed to resolve or build | `uv run caml install X --force` to retry, and read its error. Network errors are usually transient. |
| `TABPFN_TOKEN is not set (or is still the placeholder value)` | No token in the job's environment | [tabpfn.md](tabpfn.md) step 3. The export must be in `~/.profile`, not `~/.bashrc`. |
| `TabPFNLicenseError` | The TabPFN-3 model license wasn't accepted | The user accepts it on ux.priorlabs.ai (Licenses tab) |

## Jobs that fail

| Status / message | Cause | What to do |
|---|---|---|
| `killed` | Almost always the kernel's out-of-memory killer | As root: `dmesg -T \| grep -i -E 'killed process\|oom'`. Use a bigger server, `--folds 1`, or a row sample. Report it as a memory limit. |
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
| `another caml sweep is already running on ...` | A second driver started on the same sweep | `ps aux \| grep '[c]aml sweep'`. Wait, or stop the old one (`kill -TERM <pid>`); the lock frees itself when the process exits. |
| The SSH session dropped and the sweep stopped | It wasn't detached | Re-run the same command with `setsid nohup ... & disown`. Finished jobs are skipped. |
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
