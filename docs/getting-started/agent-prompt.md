# Prompt: have an AI agent benchmark your dataset (from a Mac)

Hand this prompt to an AI agent that can run shell commands on your Mac
(Claude Code, or any agent with a terminal). It sets up your Ubuntu VPS,
runs the AutoML frameworks on your dataset with CAML, monitors the run to
the end, and writes you an honest report. The Mac only sends commands;
everything heavy runs on the server.

Part 1 is for you (about 10 minutes). Part 2 is the prompt.

## Part 1: before you hand it over

### 1. Rent the server

Ubuntu 24.04, x86_64, with root SSH login. No GPU is needed.

| Your data | Server |
|---|---|
| Up to ~100k rows × 100 columns, all frameworks | 8 dedicated vCPU, 32 GB RAM, 150 GB SSD |
| Small data, or a few frameworks | 4 vCPU, 16 GB RAM, 80 GB SSD |

RAM should be at least 10 times your CSV file's size.

### 2. Give your Mac key access to it

In Terminal, one command at a time. The first creates a key (accept the
defaults); the second asks for the server's root password once:

```bash
ssh-keygen -t ed25519
```

```bash
ssh-copy-id root@SERVER_IP
```

If macOS says `ssh-copy-id: command not found`, use this instead:

```bash
cat ~/.ssh/id_ed25519.pub | ssh root@SERVER_IP 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

If you gave the key a passphrase, store it in the keychain, so the agent's
`ssh` doesn't stop at a prompt:

```bash
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

Then give the server a short name. Open `~/.ssh/config` in any text editor
(for example `nano ~/.ssh/config`) and add:

```text
Host caml-vps
  HostName SERVER_IP
  User root
  IdentityFile ~/.ssh/id_ed25519
  AddKeysToAgent yes
  UseKeychain yes
  ServerAliveInterval 30
  ServerAliveCountMax 6
```

Check it. This must print `ok` without asking for anything:

```bash
ssh -o BatchMode=yes caml-vps true && echo ok
```

The prompt only gives the agent the name `caml-vps`. **Never put the
server's password, your private key or any token into the prompt or the
chat.** The agent doesn't need them.

### 3. Get the dataset ready

- One table, one row per example, with a header row, as CSV or Parquet.
  From Excel: File > Save As > **CSV UTF-8 (Comma delimited)**. From
  Numbers: File > Export To > CSV, with the text encoding set to Unicode
  (UTF-8). `.xlsx` and `.numbers` files don't load.
- Know which column you want to predict, and which columns are IDs or only
  known after the outcome (they leak the answer). If you're not sure, the
  agent will ask.

### 4. Decide about TabPFN (optional)

TabPFN is a pretrained model from Prior Labs. It needs a free token.

- **Skip it**: the simplest choice.
- **Local `TabPFN`**: runs on your server, but its weights are licensed for
  non-commercial use only. On a server without a GPU, it refuses datasets
  above about 1,250 rows (with 5 folds).
- **Hosted `TabPFNClient`**: **uploads your data to Prior Labs' servers.**
  Only choose it if you're allowed to share the data.

For either, register at https://ux.priorlabs.ai, accept the licenses on its
Licenses tab, and create an API key. Don't paste the key anywhere: the
agent will give you a command that asks for it without showing it.

### 5. Optional

- In Claude Code, `/plugin marketplace add A1i-Tabatabaei/CAML`, then
  `/plugin install caml@caml`, loads CAML's skill automatically. The prompt
  works without it.
- The run itself is detached on the server, so it survives your Mac
  sleeping or the agent stopping. Only the monitoring pauses. For live
  monitoring, keep the Mac plugged in and awake.

## Part 2: the prompt

Fill in **My details**, then paste everything in the box into the agent.

````markdown
# Task: benchmark AutoML frameworks on my dataset with CAML, on my VPS, and monitor the run to the end

You're working on my Mac, with a shell. Use CAML
(https://github.com/A1i-Tabatabaei/CAML), an open-source tool that installs
each AutoML framework in its own environment on an Ubuntu server, runs them
all on the same folds of a dataset, scores them the same way and ranks them.
Run it on my VPS against my dataset, following the repo's own guidelines,
monitor the run until it finishes, and give me an honest, reproducible
report of which framework does best on my data.

## My details

- Server: SSH host alias `caml-vps`, from ~/.ssh/config. Key login as root
  already works (`ssh -o BatchMode=yes caml-vps true`). Provider and size:
  <e.g. 8 vCPU / 32 GB RAM / 150 GB disk>
- Dataset on this Mac: <full path, e.g. /Users/me/Downloads/churn.csv>
- Column to predict: <name>. What it means: <one line>. I expect:
  <classification / regression / not sure>
- Columns to drop (IDs, anything only known after the outcome): <list, or "ask me">
- Rows are: <independent / ordered in time by COLUMN / grouped by COLUMN
  (several rows per customer, patient, ...)>
- "Best" means: <the default metric / balanced accuracy (imbalanced
  classes) / RMSE / MAE / ...>
- Time budget: <e.g. results within 6 hours / it can run overnight>
- TabPFN: <skip / local TabPFN (non-commercial use) / also TabPFNClient: I'm
  allowed to upload this data to Prior Labs>
- Put the report and results in: <a folder on this Mac, e.g. ~/caml-run>

If anything above is blank or unclear, ask me before you touch the server,
in one message.

## How my setup works

- **This Mac is only the control station.** Here you run `ssh` and `scp`,
  and read and write files. Never install AutoML frameworks, Python
  packages or uv on the Mac, and don't run `uv sync` or `caml` here.
  Everything else runs on the server.
- The Mac has macOS's BSD tools and zsh, not GNU tools: there's no
  `timeout`, `watch` or `sha256sum` (use `shasum -a 256`), `sed -i` needs
  `''`, and `mktemp --suffix` and `date -d` don't exist. Put real work in
  scripts that run on the server (Ubuntu, GNU tools), and keep Mac-side
  commands simple.
- Commands you give **me** to paste into Terminal: one command per block,
  without `#` comments (zsh doesn't treat them as comments).
- The server runs Ubuntu 24.04. CAML lives in
  `/home/caml/caml-workspace/CAML`, and all of its commands run as the
  unprivileged `caml` user, in this shape:
  `ssh caml-vps "sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml status'"`
- Anything longer than one line goes in a script file: write it on the Mac,
  `scp` it to the server, give it to `caml` if it runs as `caml`
  (`chown caml:caml`), and run the file. Multi-line strings quoted through
  `ssh "..."` and `bash -lc '...'` have broken repeatedly in this project.
- Anything that takes more than a few minutes runs **detached** on the
  server, so it survives a dropped connection, the Mac sleeping or you
  stopping: `setsid nohup bash SCRIPT > LOG 2>&1 < /dev/null & disown`.
  Then poll its log. After a pause, re-check the real state on the server;
  never assume it.

## Ground rules (non-negotiable)

1. **Secrets never go through chat or files.** Never ask me to paste a
   password, a private key or the TabPFN token, and never print, log or
   commit one. When a secret is needed, give me the command to run myself;
   it reads the secret with a silent prompt.
2. **My data goes to my server and nowhere else.** `TabPFNClient` uploads
   it to Prior Labs: include it only if My details says so.
3. **Servers and money are my call.** Don't create, resize or delete
   servers. Tell me if this one is too small.
4. **Ask before anything destructive or costly**: deleting files on the
   server, stopping a running sweep, re-running more than about an hour of
   jobs, or changing the plan we agreed on.
5. **Don't edit CAML's code to make a framework pass.** If CAML itself
   misbehaves, keep the evidence (command, log tail, versions) for the
   maintainers' section of the report.
6. **One sweep at a time**, and no other heavy work on the server while it
   runs. CPU contention changes what each framework achieves within its
   time budget.
7. **Report honestly.** Every failed framework or fold appears in the
   report with its reason. Close results are ties. Say what you didn't
   verify.

## Step 0: read before you run anything

Clone the repo on the Mac, only to read it:
`git clone https://github.com/A1i-Tabatabaei/CAML.git ~/CAML`. If macOS
offers to install the Command Line Tools, tell me and wait (or read the
files on GitHub). Read, in this order:

1. `skills/caml-benchmark/SKILL.md`, the runbook. Follow its phases; this
   prompt adds my specifics.
2. In `skills/caml-benchmark/references/`: `vps.md`, `data-preparation.md`,
   `troubleshooting.md`, `reporting.md`, and `tabpfn.md` if TabPFN is in.
3. `README.md` ("Benchmark your own data", "Run it on a VPS") and
   `docs/operations/known-issues.md` (the open issues, `KI-nn`).

Check the version: `grep __version__ ~/CAML/src/caml/__version__.py`. From
1.0.1, `prepare-data` reads semicolon CSVs and decimal commas, and
`scripts/provision_vps.sh` works from a Mac. On 1.0.0, make sure the CSV
is comma-separated UTF-8, and provision with route A below.

Then send me your plan in under 10 lines (frameworks, folds, constraint,
estimated duration) with your questions, and wait for my OK.

## Step 1: check the server (read-only)

- `ssh -o BatchMode=yes caml-vps 'grep PRETTY /etc/os-release; uname -m; nproc; free -h | head -2; df -h / | tail -1'`
  Expect Ubuntu 24.04 on x86_64. Record the CPU count, RAM and disk for the
  report, and compare them with `SKILL.md`'s sizing table and my file's
  size (RAM at least 10 times the CSV).
- Network: `ssh caml-vps 'curl -sS -m 20 -o /dev/null -w "pypi %{http_code}\n" https://pypi.org/simple/pip/; curl -sS -m 20 https://www.openml.org/api/v1/json/task/3913 | head -c 100; echo'`
  PyPI must answer. OpenML is only needed for CAML's `test` smoke benchmark,
  not for my data. If it hangs, skip that smoke test.
- Is CAML already there?
  `ssh caml-vps 'test -d /home/caml/caml-workspace/CAML && echo present || echo absent'`.
  If it's present, don't provision again: run `uv run caml doctor` and
  `uv run caml status` as `caml`, and tell me what's installed.

## Step 2: provision (only if CAML is absent)

**Route A**, recommended from a Mac, because everything runs on the server:

```bash
ssh caml-vps 'command -v git >/dev/null || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git)'
ssh caml-vps 'test -d /tmp/CAML || git clone https://github.com/A1i-Tabatabaei/CAML.git /tmp/CAML'
ssh caml-vps 'bash /tmp/CAML/scripts/bootstrap_vps.sh'
ssh caml-vps 'sudo -iu caml bash /tmp/CAML/scripts/setup_workspace.sh'
```

**Route B**, 1.0.1 or newer only: `cd ~/CAML && scripts/provision_vps.sh caml-vps`.

`bootstrap_vps.sh` installs the apt baseline, uv, the `caml` user, and swap
if RAM is under 8 GB. `setup_workspace.sh` clones CAML into
`~/caml-workspace`, runs `uv sync`, then `caml doctor`. Both are safe to
re-run. If your shell tool can't wait 15 minutes, run them detached and
poll the log. **Check**: `caml doctor` reports no `MISSING`.

## Step 3: install the frameworks (detached, 30–60 minutes)

Install only what we'll run. NaiveAutoML is never included (an upstream bug
fails every task). Put this in `/home/caml/install_fw.sh`, then run it
detached as `caml` with its output in `~/install.log`:

```bash
#!/usr/bin/env bash
cd ~/caml-workspace/CAML || exit 1
for fw in AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML; do
  echo "=== $fw $(date -u +%H:%M:%S)"
  uv run caml install "$fw" || echo "!!! $fw FAILED"
done
uv run caml status
```

Retry a failed install once with `uv run caml install NAME --force`. If it
fails again, read the error, check `references/troubleshooting.md`, and
tell me. Don't hold the run up: we can go ahead with the others.

If OpenML answered in step 1, smoke-test one framework:
`uv run caml run FLAML --benchmark test --constraint test`. It takes about
6 minutes and must print real scores, not NaN.

## Step 4: TabPFN (only if My details asks for it)

Follow `references/tabpfn.md`. Give me its step-3 commands to run myself
(`ssh caml-vps`, then `sudo -iu caml`), then confirm with its "token-set"
check, which doesn't print the token. On a CPU server, local `TabPFN`
refuses training splits above 1,000 rows. With 5 folds, skip it above about
1,250 rows and say why in the report. Include `TabPFNClient` only with my
upload consent.

## Step 5: the data

1. Look before copying: `ls -lh`, `file -I` (the encoding) and
   `head -c 800` of my file. Show me the header and confirm the target and
   the columns to drop. For an Excel or Numbers file (`.xlsx`, `.numbers`),
   ask me to export a CSV UTF-8; don't install converters.
2. Copy it to the server, readable only by `caml`, quoting paths that
   contain spaces:

   ```bash
   ssh caml-vps 'install -d -o caml -g caml -m 700 /home/caml/data'
   scp "<my file>" caml-vps:/home/caml/data/
   ssh caml-vps 'chown -R caml:caml /home/caml/data'
   ```

   The checksums must match: `shasum -a 256 "<my file>"` on the Mac, and
   `sha256sum /home/caml/data/<file>` on the server.
3. Prepare it on the server as `caml` (the YAML it writes holds absolute
   server paths):
   `uv run caml prepare-data /home/caml/data/<file> --target <col> --drop <col> --name <short_name> --folds 5`.
   Read me its output: the task type and why, the class counts, and every
   `WARNING`. **Get my OK on the task type**; fix it with `--type` if it's
   wrong. If the rows are ordered in time or grouped, random folds leak:
   follow "When random folds are wrong" in `data-preparation.md`, and check
   with me first.

## Step 6: plan and launch the sweep

- Frameworks: AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT
  GAMA FEDOT SapientML, minus any that failed to install, plus TabPFN or
  TabPFNClient as agreed. (`caml sweep` refuses to start if a listed
  framework isn't installed.)
- Constraint: `quick` (5 minutes per job, all cores) for this screening.
  Expect frameworks × folds × about 8 minutes, so 9 × 5 × 8 is about 6 hours.
  If that's over my time budget, propose fewer folds (re-run
  `prepare-data` with `--folds 3 --force`) or fewer frameworks, and wait
  for my OK.
- Keep the settings in one file on the server, `/home/caml/sweep.env`,
  owned by `caml`:

  ```bash
  FW="AutoGluon FLAML H2OAutoML LightAutoML MLJARSupervised TPOT GAMA FEDOT SapientML"
  B=/home/caml/caml-workspace/CAML/input/datasets/<short_name>/<short_name>.yaml
  C=quick
  ```

  with the launcher `/home/caml/run_sweep.sh`:

  ```bash
  #!/usr/bin/env bash
  . ~/sweep.env
  cd ~/caml-workspace/CAML && uv run caml sweep $FW --benchmark "$B" --constraint "$C"
  ```

- Preview it as `caml`: `. ~/sweep.env && cd ~/caml-workspace/CAML && uv run caml sweep $FW --benchmark "$B" --constraint "$C" --dry-run | tail -15`
- Launch it as `caml`:
  `setsid nohup bash ~/run_sweep.sh > ~/sweep.log 2>&1 < /dev/null & disown`.
  Tell me the start time (UTC), the number of jobs and the ETA.

`caml sweep` runs one isolated job at a time, fold by fold, records each in
a ledger under `output/sweeps/<short_name>-quick/`, and resumes where it
stopped when the same command is run again.

## Step 7: monitor until it finishes

Install this status script once: write it on the Mac and `scp` it to
`/root/caml_status.sh`. Each check is then one call,
`ssh caml-vps 'bash /root/caml_status.sh'`, which doesn't disturb the run.

```bash
#!/usr/bin/env bash
# One-shot status of the CAML sweep. Run as root.
. /home/caml/sweep.env
echo "== $(date -u '+%F %T') UTC | load $(cut -d' ' -f1-3 /proc/loadavg) | $(uptime -p)"
free -h | head -2
df -h /home | awk 'NR==2 {print "disk free: " $4 " of " $2}'
pgrep -f 'caml sweep' >/dev/null && echo "sweep driver: running" || echo "sweep driver: NOT running"
echo "== OOM kills since boot: $(dmesg 2>/dev/null | grep -ciE 'killed process|out of memory')"
echo "== sweep.log"; tail -n 8 /home/caml/sweep.log
sudo -iu caml bash -lc "cd ~/caml-workspace/CAML && uv run caml sweep $FW --benchmark '$B' --constraint $C --dry-run | sed -n '/^FRAMEWORK/,\$p'"
```

- Check every 20–30 minutes, not in a tight loop: use your environment's
  scheduling, or a background wait.
- Keep a log on the Mac, `<report folder>/monitoring-log.md`: the time, jobs
  done out of the total, failures so far, memory, and anything you did and
  why.
- Update me at milestones only: installs finished, data prepared, sweep
  launched (with the ETA), any new failure pattern, about every 2 hours,
  and at the end.
- Act on what you see:

  | You see | Do |
  |---|---|
  | A job ends `error` | Read the end of `output/sweeps/<name>/logs/<fw>.<task>.<fold>.log` and classify it with `references/troubleshooting.md`: a framework limitation, a budget or memory limit, or a CAML bug. Don't retry yet. |
  | `killed` | Out of memory: `dmesg -T \| grep -iE 'killed process\|oom' \| tail`. If one framework keeps getting killed, tell me (a bigger server, fewer folds, or drop it). |
  | `timeout` | The framework overran 2 × its budget + 20 minutes. Note it, and check the log's end for a hang. |
  | `sweep driver: NOT running` while jobs are pending | Read the end of `sweep.log`. If the sweep was interrupted (a reboot, a kill), launch `run_sweep.sh` again: finished jobs are skipped. If it crashed, tell me. |
  | Under 10 GB of free disk, or swap filling up | Tell me. |
  | The same failure on every fold of one framework | Tell me now, not at the end. |

- When every job is done: if some failed for reasons that could pass on a
  second try (a network error, a one-off memory spike), propose one rerun
  with `--retry-failed` added to the sweep command, with its time cost, and
  run it only with my OK. Then run `uv run caml doctor` to check that no
  H2O JVM was left running.

## Step 8: results and report

1. On the server: `uv run caml leaderboard --benchmark "$B" --constraint "$C"`,
   then the same with `--markdown`.
2. Copy the evidence to the Mac:
   `scp -r caml-vps:/home/caml/caml-workspace/CAML/output "<report folder>/output"`
   and
   `scp -r caml-vps:/home/caml/caml-workspace/CAML/input/datasets/<short_name> "<report folder>/dataset"`.
3. Write `<report folder>/report.md`, following `references/reporting.md`:
   - **The leaderboard**: rank, framework, mean ± standard deviation of the
     primary metric, folds that succeeded, mean training time.
   - **Ties**: differences smaller than about one standard deviation are
     ties; say so. With one dataset there's no significance test
     (`caml compare` needs two or more datasets).
   - **Failures**: every failed framework or fold, with its reason and its
     classification.
   - **The setup**: the CAML version and revision (the `app_version`
     column), each framework's `version`, the constraint, folds and seed,
     the server's CPU and RAM, and the dataset's SHA-256 from
     `dataset.json`.
   - **What it means**: a 5-minute budget favors fast frameworks. If the
     choice matters, recommend re-running the top 2–3 under `1h8c` (1 hour,
     8 cores per job), with the time that would take.
   - **The next step**: retrain the winner on all the data with its own
     API. CAML compares frameworks; it doesn't deploy models.
   - **Notes for the CAML maintainers**: this is one of the first runs of
     `prepare-data` with real frameworks (known issue KI-15). List anything
     that broke, confused you or was missing from the docs, with commands
     and log excerpts. Draft it; don't post anything. I'll file it.
4. If I later ask you to write an article, paper or post from these
   results, cite CAML, AMLB and the frameworks (the BibTeX is in
   `SKILL.md`), and tell me that you added the citation.

## Step 9: wrap up

Tell me what's left on the server (the frameworks, my data in
`/home/caml/data`, the prepared folds, the outputs), and ask whether to
delete my data there. Remind me that the server bills until I delete it in
my provider's console. Delete nothing without my yes.

## Stop and ask me when

- the server's OS, architecture, memory or disk don't fit the plan;
- the task type, the target or the columns to drop are unclear;
- the plan won't fit my time budget;
- a framework fails on every fold, or memory kills keep happening;
- you'd need more money, a different server, or to send my data anywhere
  new;
- the repo's docs contradict this prompt (tell me where, and follow the
  safer of the two).

## Done means

- [ ] Every planned job is `ok`, or its failure is explained.
- [ ] `report.md`, `monitoring-log.md`, `output/` and `dataset/` are in my
      report folder.
- [ ] You've told me what's left on the server and that it still bills.
````

## After the run

The frameworks stay installed, so a longer comparison of the top 2–3 is
cheap to start: ask the agent to re-run them under `1h8c` on the same
server. When you're finished, copy anything you still need, and delete the
server in your provider's console.
