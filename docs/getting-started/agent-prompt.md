# Prompts for an AI agent (Windows, macOS, Linux)

Hand one of these prompts to an AI agent that can run commands on your
computer: Claude Code, Codex, Cursor, Copilot, or any agent with a shell.
The agent:

- sets up your Ubuntu VPS;
- runs the AutoML frameworks on your dataset with CAML;
- monitors the run to the end;
- writes you an honest report, plus a **field report** of everything that
  went wrong along the way.

Your computer only sends commands over SSH. CAML itself always runs on the
Ubuntu server.

The same three prompts are in the README, under
[For AI agents](https://github.com/A1i-Tabatabaei/CAML#for-ai-agents). Part 1 is for you (about 10
minutes, or less if you let the agent walk you through SSH). Part 2 is the
prompts. Part 3 is what to do with the field report.

## Part 1: before you paste

### 1. Rent the server

Ubuntu 24.04, x86_64, with root SSH login. No GPU is needed.

| Your data | Server |
|---|---|
| Up to ~100k rows × 100 columns, all frameworks | 8 dedicated vCPU, 32 GB RAM, 150 GB SSD |
| Small data, or a few frameworks | 4 vCPU, 16 GB RAM, 80 GB SSD |

RAM should be at least 10 times your CSV file's size. Keep the server's IP
address and root password from your provider at hand. The password is for
you, not for the agent.

### 2. Give your computer key access to it

You can skip this and write "key login not set up yet" on the prompt's
Server line: the agent then walks you through the same steps. Either way,
**you** type the server password, never the agent.

**Windows** (PowerShell; press Enter at each `ssh-keygen` question):

```powershell
ssh-keygen -t ed25519
```

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@SERVER_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

```powershell
@"
Host caml-vps
  HostName SERVER_IP
  User root
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 30
  ServerAliveCountMax 6
"@ | Add-Content -Encoding ascii $env:USERPROFILE\.ssh\config
```

If `ssh` isn't found, add it: Settings > System > Optional features > Add a
feature > OpenSSH Client. Create the config exactly as above: Notepad and
PowerShell 5.1's `>` save it in ways ssh can't read.

**macOS** (Terminal; one command at a time):

```bash
ssh-keygen -t ed25519
```

```bash
ssh-copy-id root@SERVER_IP
```

If you gave the key a passphrase, store it in the keychain:
`ssh-add --apple-use-keychain ~/.ssh/id_ed25519`. Then open
`~/.ssh/config` (for example `nano ~/.ssh/config`) and add:

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

**Linux**: the same as macOS, without the keychain lines (`AddKeysToAgent`
and `UseKeychain`).

**Check it** on any OS. This must print `ok` without asking for anything:

```bash
ssh -o BatchMode=yes caml-vps echo ok
```

**Never put the server's password, your private key or any token into the
prompt or the chat.** The agent doesn't need them.

### 3. Get the dataset ready

- One table, one row per example, with a header row, as CSV or Parquet.
- **Excel on Windows**: File > Save As > **CSV UTF-8 (Comma delimited)**.
  The plain "CSV (Comma delimited)" works too, but it isn't UTF-8, and the
  agent will have to convert it.
- **Excel on a Mac**: File > Save As > CSV UTF-8. **Numbers**: File >
  Export To > CSV, with the text encoding set to Unicode (UTF-8).
- **LibreOffice**: File > Save As > Text CSV, with the character set
  Unicode (UTF-8).
- `.xlsx` and `.numbers` files don't load. Semicolon separators and decimal
  commas (`1,5`) are fine.
- If the file is in OneDrive or iCloud Drive, make sure it's downloaded to
  this computer.
- Know which column you want to predict, and which columns are IDs or only
  known after the outcome (they leak the answer). If you're not sure, the
  agent will ask.

### 4. Decide about TabPFN (optional)

TabPFN is a pretrained model from Prior Labs. It needs a free key.

- **Skip it**: the simplest choice.
- **Local `TabPFN`**: runs on your server, but its weights are licensed for
  non-commercial use only. On a server without a GPU, it refuses datasets
  above about 1,250 rows (with 5 folds).
- **Hosted `TabPFNClient`**: **uploads your data to Prior Labs' servers.**
  Only choose it if you're allowed to share the data.

For either, register at https://ux.priorlabs.ai, accept the licenses on its
Licenses tab, and create an API key. Don't paste the key anywhere. When the
agent asks, run `ssh -t caml-vps camlctl tabpfn-token` yourself, in your own
terminal. It asks for the key without showing it.

### 5. Optional

- In Claude Code, `/plugin marketplace add A1i-Tabatabaei/CAML`, then
  `/plugin install caml@caml`, loads CAML's skill automatically. The prompts
  work without it.
- The run itself is detached on the server, so it survives your computer
  sleeping or the agent stopping; only the monitoring pauses. For live
  monitoring, keep the computer plugged in and awake.

## Part 2: the prompts

Pick your OS, fill in **My details** (replace each `<...>`), and paste the
whole block into the agent. Every prompt tells the agent to confirm the OS
and shell first, and to switch profiles if you picked the wrong one.

### Windows

<!-- prompt:windows -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on Windows, and you have a shell on this PC. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This PC only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. C:\Users\me\Downloads\churn.csv>
- Predict: <column> (<what it means>). Task: <classification / regression / not sure>
- Drop: <ID columns and anything only known after the outcome, or "ask me">
- Rows are: <independent / ordered in time by COLUMN / grouped by COLUMN>
- "Best" means: <the default metric / balanced accuracy / RMSE / ...>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip / local TabPFN, non-commercial use / also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. C:\caml-run>

How to work:
1. Find out which shell you're in (PowerShell, Git Bash, cmd or WSL; operator-windows.md shows how), and confirm this is Windows. If it isn't, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-windows.md (this PC: commands and gotchas), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Before you change anything on the server, send me your plan in under 10 lines (frameworks, folds, constraint, estimated duration) with your questions, and wait for my OK.

Rules:
- Never ask me for, or handle, passwords, private keys or the TabPFN key. When one is needed, give me the command to run myself.
- My data goes to my server and nowhere else.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-windows.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this PC and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on Windows.

Done means: every planned job is ok or its failure is explained; report.md (following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-windows.md are in my report folder; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:windows -->

### macOS

<!-- prompt:macos -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on macOS, and you have a shell on this Mac. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This Mac only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. /Users/me/Downloads/churn.csv>
- Predict: <column> (<what it means>). Task: <classification / regression / not sure>
- Drop: <ID columns and anything only known after the outcome, or "ask me">
- Rows are: <independent / ordered in time by COLUMN / grouped by COLUMN>
- "Best" means: <the default metric / balanced accuracy / RMSE / ...>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip / local TabPFN, non-commercial use / also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. ~/caml-run>

How to work:
1. Confirm this is macOS (`uname -s` prints Darwin) and note the shell. If it isn't, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-macos.md (this Mac: commands and gotchas), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Before you change anything on the server, send me your plan in under 10 lines (frameworks, folds, constraint, estimated duration) with your questions, and wait for my OK.

Rules:
- Never ask me for, or handle, passwords, private keys or the TabPFN key. When one is needed, give me the command to run myself.
- My data goes to my server and nowhere else.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-macos.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this Mac and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on macOS.

Done means: every planned job is ok or its failure is explained; report.md (following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-macos.md are in my report folder; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:macos -->

### Linux

<!-- prompt:linux -->
```text
Benchmark the AutoML frameworks on my dataset with CAML, on my Ubuntu server, and monitor the run until it finishes.

I'm on Linux, and you have a shell on this machine. CAML (https://github.com/A1i-Tabatabaei/CAML) installs each AutoML framework in its own environment on an Ubuntu 24.04 server, runs them all on the same folds of my data, and ranks them. This machine only sends commands over SSH and keeps the reports: install nothing on it.

My details (if anything is blank or unclear, ask me in one message before you touch the server):
- Server: <SSH alias caml-vps, root key login works | IP address, key login not set up yet: walk me through it, I'll type the password myself>
- Server size: <e.g. 8 vCPU / 32 GB RAM / 150 GB disk, at PROVIDER>
- Dataset: <full path, e.g. /home/me/data/churn.csv>
- Predict: <column> (<what it means>). Task: <classification / regression / not sure>
- Drop: <ID columns and anything only known after the outcome, or "ask me">
- Rows are: <independent / ordered in time by COLUMN / grouped by COLUMN>
- "Best" means: <the default metric / balanced accuracy / RMSE / ...>
- Time budget: <e.g. results within 6 hours>
- TabPFN: <skip / local TabPFN, non-commercial use / also TabPFNClient: I may upload this data to Prior Labs>
- Report folder: <e.g. ~/caml-run>

How to work:
1. Confirm this is Linux (`uname -s`), and whether it's WSL. If it isn't Linux, tell me and use the matching profile instead. Then read these files from the CAML repo (clone it read-only, or read them on GitHub), in order: skills/caml-benchmark/SKILL.md (the runbook: follow its phases), skills/caml-benchmark/references/operator-linux.md (this machine: commands and gotchas), references/camlctl.md (the one server command), references/field-report.md, and the other references when SKILL.md points to them.
2. Drive the server only with `ssh caml-vps camlctl ...`, as the docs show. Run setup, the installs and the sweep as camlctl jobs, and check on them with `camlctl wait` or `camlctl status` every 20-30 minutes, never in a tight loop.
3. Before you change anything on the server, send me your plan in under 10 lines (frameworks, folds, constraint, estimated duration) with your questions, and wait for my OK.

Rules:
- Never ask me for, or handle, passwords, private keys or the TabPFN key. When one is needed, give me the command to run myself.
- My data goes to my server and nowhere else.
- Creating, resizing or deleting servers, and anything else that costs money, is my call.
- Ask before deleting files, stopping a running sweep, or re-running more than an hour of jobs.
- Don't edit CAML's code to make something pass: work around it, and record it in the field report.
- One sweep at a time on the server.
- Report honestly: every failed framework or fold, with its reason. Close results are ties.

Field report (required): before your first command, create caml-field-report-linux.md in my report folder from the template in references/field-report.md, and keep it up to date as you go. Record every error, bug, wrong or unclear doc, workaround and gotcha you hit, on this machine and on the server, when it happens: the exact command, the full error, the cause, the fix that worked, and what CAML should change. Also list what worked first time. Leave out secrets, my server's IP and my data's values. I'll send this file to the CAML maintainer, so that CAML works better on Linux.

Done means: every planned job is ok or its failure is explained; report.md (following references/reporting.md), monitoring-log.md, the unpacked results bundle and caml-field-report-linux.md are in my report folder; and you've told me what's left on the server, which bills until I delete it.
```
<!-- /prompt:linux -->

## Part 3: the field report

At the end, your report folder holds `caml-field-report-windows.md`,
`caml-field-report-macos.md` or `caml-field-report-linux.md`. It lists:

- every error, bug, wrong or unclear doc, workaround and gotcha the agent
  hit, on your computer and on the server, with the commands, errors and
  fixes;
- what worked first time;
- your environment (OS, shell, agent, server size).

Its template is in
[`references/field-report.md`](https://github.com/A1i-Tabatabaei/CAML/blob/main/skills/caml-benchmark/references/field-report.md).

**Please send it to the CAML maintainer.** That's how CAML gets fixed for
the next person on your OS. The easiest way is a new GitHub issue with the
**Field report** template, with the file attached:
https://github.com/A1i-Tabatabaei/CAML/issues/new/choose. If you were asked
to send it another way, do that instead.

Before you send it, skim it. It shouldn't contain passwords, keys, tokens,
your server's IP address or rows of your data. The agent is told to leave
these out.

## After the run

The frameworks stay installed, so a longer comparison of the top 2–3 is
cheap to start: ask the agent to re-run them under `1h8c` on the same
server. When you're finished, copy anything you still need, and delete the
server in your provider's console.
