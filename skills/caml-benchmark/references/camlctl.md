# camlctl: the server command

`camlctl` is installed on the CAML server at `/usr/local/bin/camlctl`. From
any operator machine (Windows, macOS or Linux), every server action has the
same shape:

```bash
ssh caml-vps camlctl <command> [args]
```

The arguments are plain words: no quotes, no `$`, no spaces inside a value.
That line works unchanged in PowerShell, cmd, Git Bash, zsh and bash.
`camlctl` handles the rest itself: running as the `caml` user, working in the
repo, detaching long jobs, reporting status, taking in your dataset and
bundling the results. Before it existed, commands like
`ssh HOST "sudo -iu caml bash -lc 'cd ... && uv run caml ...'"` broke
repeatedly on quoting, and they break differently in every local shell.

`camlctl` runs as root. If you log in as a passwordless sudoer instead (for
example `ubuntu`), it re-runs itself with `sudo -n`. `camlctl help` prints the
summary below.

## Output conventions (for agents)

- Reports are `key: value` lines (`status: ok`, `sha256: ...`), so you can
  parse them. The last line of `info` is `checks: ok` or
  `checks: N warning(s)`, with each warning on its own `warning:` line before it.
- Exit codes: `0` ok, `1` failed, `2` usage error, `3` conflict (already
  running, or would overwrite), `124` `wait` timed out while the job is still running.
- Errors go to stderr, prefixed `camlctl:`, and say what to run next.

## Setup and health

| Command | What it does |
|---|---|
| `info [--offline]` | Read-only facts: OS, arch, CPUs, RAM, swap, free disk, GPU, reachability of PyPI, GitHub, the PyTorch index and OpenML, whether the `caml` user, uv and CAML exist, running jobs, and warnings. Safe at any time, including before setup (run it as `bash /opt/caml-src/scripts/camlctl info` until setup has installed it). |
| `setup [--detach] [--ref REF] [--src ARCHIVE_OR_URL]` | Installs everything: `bootstrap_vps.sh` (apt baseline, uv, the `caml` user, swap below 8 GB, a scoped sudoers entry), then `setup_workspace.sh` as `caml` (the workspace, `uv sync`, `caml doctor`), then `camlctl` itself and `~caml/data`. Idempotent. Takes 5–15 minutes: use `--detach`, then `camlctl wait setup 540`. `--ref` checks out a tag or branch (for example `v1.1.0`); `--src` installs from a pushed `git archive` instead of GitHub. |
| `version` | camlctl's version, and CAML's version and git revision. |
| `update [--ref REF] [--force]` | `git pull` (or check out REF) in the workspace, `uv sync`, and refresh camlctl. It refuses while a run, sweep or job is active. Archive deploys (`provision_vps.sh`) update with `scripts/sync_vps.sh` instead. |
| `tabpfn-token [--check\|--remove]` | Stores the TabPFN key for `caml`, so it never passes through chat. The user runs it themselves, in a real terminal: `ssh -t caml-vps camlctl tabpfn-token`. `--check` prints `token-set` or `token-missing`, never the key. |

## Work (as `caml`, in `~caml/caml-workspace/CAML`)

| Command | What it does |
|---|---|
| `caml ARGS...` | `uv run caml ARGS...`, with the exit code passed through. For example: `camlctl caml status`, `camlctl caml doctor`, `camlctl caml prepare-data ...`, `camlctl caml leaderboard ...`. Benchmark paths can be relative to the repo: `--benchmark input/datasets/churn/churn.yaml`. |
| `install [--force] FW...` | Installs several frameworks one after another, keeps going past a failure, and ends with `installed: ...` and `failed: ...` lines (exit 1 if any failed). `install --all` runs `caml install --all`. |
| `dataset FILE [--name NAME] [--from-encoding ENC] [--replace]` | Moves an uploaded file into `~caml/data/` (owned by `caml`, mode 600) and describes it: `path`, `bytes`, `sha256` (compare it with your local hash), `format`, `encoding`, `line_endings`, `separator`, `columns`, `rows`, `header`, then `status` (`ok`, `needs-conversion` or `unsupported`) and the `next:` or `fix:` command. `--from-encoding WINDOWS-1252` (Excel on Windows) or `MACINTOSH` (old Mac exports) converts the file to UTF-8 and keeps the original as `NAME.orig`. An `.xlsx` workbook is refused with export instructions. It never overwrites a different file of the same name without `--replace`. |
| `script FILE [ARGS...]` | Runs a script you uploaded, as `caml`, in the repo: `.py` files with `uv run python` (pandas and scikit-learn available), anything else with `bash`. It strips Windows CRLF line endings first. Use it for anything longer than one command. |

## Long jobs

A job is any of `caml`, `install`, `script` or `setup`, run detached in its
own session. It survives the SSH connection dropping, the laptop sleeping
and the agent stopping.

| Command | What it does |
|---|---|
| `start JOB caml\|install\|script\|setup ARGS...` | Starts a job and returns at once. JOB is a name you choose (letters, digits, `.`, `_`, `-`). It refuses (exit 3) if a job of that name is still running; a finished job's files move to `history/`. |
| `jobs` | Every job: state (`running`, `done`, `failed`, `lost`), exit code, start time, elapsed time and command. `lost` means no exit code and no process: the server rebooted, or something killed it with SIGKILL. |
| `logs JOB [LINES]` | A one-line summary, then the end of the job's log (40 lines by default). |
| `wait JOB [SECONDS]` | Blocks until the job ends or SECONDS pass (default 540, max 3600), then prints the summary and the last 15 log lines. Exit 0 = done, 1 = failed, 124 = still running. Pick SECONDS below your shell tool's timeout. |
| `stop JOB` | SIGTERM to the job's whole session (a sweep then kills its current framework job and exits, leaving that job unrecorded so a re-run resumes it), SIGKILL after 60 s for anything left, including stray children. Ask the user before stopping a sweep. |
| `status` | One screen for monitoring: time, uptime, load, memory and swap, free disk, OOM kills since boot, the job list, and for the three newest sweep jobs, the last progress line plus the sweep's status table. It uses `caml sweep --dry-run`, which reads the ledger and is safe while the sweep runs. |
| `bundle [NAME]` | Packs `output/`, the prepared datasets (`input/datasets/`), the job logs and a `server-info.txt` into `~/caml-bundles/NAME.tar.gz`, in the SSH user's home. It prints the `copy:` (scp) and `unpack:` (tar) commands. Plain files only, so it unpacks with Windows' `tar.exe` too. |

Job files live in `/var/lib/camlctl/jobs/` (`JOB.log`, `.cmd`, `.args`,
`.started`, `.pid`, `.exit`, `.ended`).

## The whole flow

```bash
ssh caml-vps "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
ssh caml-vps "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
ssh caml-vps bash /opt/caml-src/scripts/camlctl info
ssh caml-vps bash /opt/caml-src/scripts/camlctl setup --detach
ssh caml-vps camlctl wait setup 540
ssh caml-vps camlctl start install install AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML
ssh caml-vps camlctl wait install 540
scp "/path/to/My Data.csv" caml-vps:churn.csv
ssh caml-vps camlctl dataset churn.csv
ssh caml-vps camlctl caml prepare-data /home/caml/data/churn.csv --target churned --drop customer_id --name churn --folds 5
ssh caml-vps camlctl caml sweep FLAML AutoGluon --benchmark input/datasets/churn/churn.yaml --constraint quick --dry-run
ssh caml-vps camlctl start sweep caml sweep FLAML AutoGluon --benchmark input/datasets/churn/churn.yaml --constraint quick
ssh caml-vps camlctl status
ssh caml-vps camlctl caml leaderboard --benchmark input/datasets/churn/churn.yaml --constraint quick --markdown
ssh caml-vps camlctl bundle churn-results
scp caml-vps:caml-bundles/churn-results.tar.gz .
```

Repeat each `wait` until it exits 0. Exit 124 means the job is still
running. The first two lines are the only raw shell commands: one pair of
double quotes, with no `$`, backtick, `%` or `!` inside, which every local
shell passes through unchanged.

## When camlctl itself misbehaves

`camlctl` is new in 1.1.0. CI runs this whole flow as root over SSH on
Ubuntu 24.04 on every push (`tests/e2e/agent_flow.sh`), but real servers
differ. If a camlctl command fails in a way its message doesn't explain,
you can fall back to the old shape for that one step:
`ssh caml-vps "sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml status'"`.
It follows the same quoting rule, so it works from every shell. Record the
failure in your field report ([field-report.md](field-report.md)).
