# Operator profile: Windows

You, the agent, run on the user's Windows PC. CAML runs on their Ubuntu
24.04 server. This PC only sends commands over SSH, copies files with
`scp`, and keeps the reports. **Install nothing on it**: no Python packages,
no uv, no AutoML frameworks, no WSL, no converters.

Everything on the server goes through `ssh caml-vps camlctl ...`
([camlctl.md](camlctl.md)). That line is the same in every Windows shell.
Only the local file commands below differ.

## 1. Which shell are you in?

| Check | Means |
|---|---|
| `$PSVersionTable.PSVersion` prints a version | PowerShell. 5.1 is Windows PowerShell, the one Windows ships; 7.x is PowerShell 7. |
| `uname -s` prints `MINGW64_NT-...` or `MSYS_NT-...` | Git Bash. Claude Code's shell tool on Windows uses it. |
| `uname -s` prints `Linux`, and `/proc/version` mentions `microsoft` | WSL. Use [operator-linux.md](operator-linux.md), plus [the WSL notes](#wsl) below. |
| `ver` prints `Microsoft Windows [Version ...]` | cmd.exe. Prefer PowerShell: `powershell -NoProfile -Command "..."`. |

Write the Windows version (`[Environment]::OSVersion.VersionString`, or
`cmd /c ver` from Git Bash), the shell and its version, and `ssh -V` into
the field report's Environment section before you start.

## 2. SSH access

Check it. This must print `ok` without asking for anything:

```powershell
ssh -o BatchMode=yes caml-vps echo ok
```

If it fails, the user sets it up once. They run these themselves; the copy
step asks for the server's root password, which never goes through you.

1. **The OpenSSH client.** `Get-Command ssh, scp` should find both. It's
   built into Windows 10 (1809 and later) and 11. If it's missing: Settings >
   System > Optional features > Add a feature > OpenSSH Client.
2. **A key.** Run `ssh-keygen -t ed25519` and press Enter at each question.
   An empty passphrase avoids the next point.
3. **A passphrase-protected key** needs the ssh-agent service, which is off
   by default. In an administrator PowerShell, run
   `Get-Service ssh-agent | Set-Service -StartupType Automatic`, then
   `Start-Service ssh-agent`, then (as the user) `ssh-add`.
4. **Copy the key to the server.** Windows has no `ssh-copy-id`:

   ```powershell
   type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@SERVER_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
   ```

   The `tr -d '\r'` removes the CRLF that PowerShell's pipe adds.
5. **The host alias.** Append it as ASCII:

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

   Don't create the file with `>`, `Out-File` or Notepad. Windows
   PowerShell 5.1's `>` and `Out-File` write UTF-16, which ssh can't parse,
   and Notepad tends to save a new `config` as `config.txt`. Never add
   `UseKeychain` (macOS only) to a Windows config.

PowerShell, cmd and Git Bash all use `%USERPROFILE%\.ssh`, so one setup
serves all three. WSL has its own.

## 3. The quoting rule

- Server work: `ssh caml-vps camlctl COMMAND plain words`. No quotes needed.
- A raw shell command on the server (only setup's first two steps need one):
  wrap it in **one pair of double quotes**, with no `$`, backtick, `%`, `!` or
  `"` inside. PowerShell expands `$` and backtick escapes inside double
  quotes, and cmd expands `%VAR%`. Single quotes don't quote anything in cmd.
- Anything longer: write a script file, `scp` it over, and run
  `ssh caml-vps camlctl script NAME.sh`. It strips CRLF line endings, which
  Windows editors (and some agent file tools on Windows) write.
- Server file names: simple words only. Rename on upload:
  `scp "C:\Users\me\My Data (final).csv" caml-vps:churn.csv`.

## 4. Local commands

| Task | PowerShell | Git Bash |
|---|---|---|
| OS version | `[Environment]::OSVersion.VersionString` | `cmd //c ver` |
| Does the file exist, and how big? | `Get-Item "C:\path\data.csv" \| Select-Object Length` | `ls -l "/c/path/data.csv"` |
| First lines | `Get-Content "C:\path\data.csv" -TotalCount 5` | `head -n 5 "/c/path/data.csv"` |
| SHA-256 | `(Get-FileHash -Algorithm SHA256 "C:\path\data.csv").Hash.ToLower()` | `sha256sum "/c/path/data.csv"` |
| Upload | `scp "C:\path\My Data.csv" caml-vps:churn.csv` | `scp "/c/path/My Data.csv" caml-vps:churn.csv` |
| Report folder | `New-Item -ItemType Directory -Force C:\caml-run` | `mkdir -p /c/caml-run` |
| Download a bundle | `scp caml-vps:caml-bundles/NAME.tar.gz C:\caml-run\` | `scp caml-vps:caml-bundles/NAME.tar.gz /c/caml-run/` |
| Unpack it | `tar -xzf C:\caml-run\NAME.tar.gz -C C:\caml-run` | `cd /c/caml-run && tar -xzf NAME.tar.gz` |
| Pause | `Start-Sleep -Seconds 60` | `sleep 60` |

Compare hashes ignoring case: `Get-FileHash` prints upper case, `camlctl
dataset` lower case. The `.ToLower()` above handles it.

## 5. Gotchas

- **No `&&` in Windows PowerShell 5.1.** It's a parse error there (PowerShell
  7 has it). Run one command per call, or separate them with `;` and check
  `$LASTEXITCODE`.
- **`curl` is not curl** in Windows PowerShell 5.1. It's an alias of
  `Invoke-WebRequest`. Use `curl.exe`, or read files on GitHub with your
  own web tool.
- **Empty and quoted arguments.** Windows PowerShell 5.1 drops an empty
  string argument (`ssh-keygen -N ""` fails) and strips `"` inside an
  argument to a native program. Let tools prompt, or keep the argument free
  of quotes. PowerShell 7.3+ fixed both.
- **`$` in a remote command** is expanded by PowerShell before ssh sees it
  (`"echo $HOME"` sends your Windows home path). This is why the quoting rule
  bans it.
- **Git Bash path conversion.** Git Bash rewrites arguments that start with
  `/` into Windows paths, but only for native Windows programs. Its own
  `ssh` and `scp` are not affected, so `ssh caml-vps camlctl dataset
  /home/caml/data/x.csv` is safe. If `ssh` resolves to
  `C:\Windows\System32\OpenSSH\ssh.exe` instead (`command -v ssh`), prefix
  the command with `MSYS_NO_PATHCONV=1`.
- **Git Bash's tar** is GNU tar, which reads `C:\...` or `C:/...` as a
  remote host. Use relative paths after `cd`, or add `--force-local`. In
  PowerShell, `tar` is Windows' own `tar.exe`, which has no such problem.
- **Line endings.** Clones keep LF (the repo's `.gitattributes`), so
  `scripts/*.sh` stay runnable on the server. Files *you* write for the
  server may get CRLF: send them through `camlctl script`, or write them with
  LF.
- **OneDrive.** Desktop and Documents are often OneDrive folders with
  Files On-Demand. A file that shows a cloud icon isn't on disk, and `scp`
  of it can fail or hang. Ask the user to choose "Always keep on this
  device", or to copy the dataset elsewhere first.
- **Long paths.** Unpack bundles into a short folder such as `C:\caml-run`.
  Deep result paths can pass Windows' 260-character limit.
- **The TabPFN key** needs a real terminal. The user runs
  `ssh -t caml-vps camlctl tabpfn-token` in Windows Terminal or PowerShell
  themselves, not through your shell tool.
- **Sleep.** A detached job keeps running on the server whatever the PC
  does; only your monitoring pauses. For live monitoring, the user sets
  sleep to "Never" while plugged in (Settings > System > Power).
  Don't change power settings yourself.
- **The repo's skill symlink.** `.claude/skills/caml-benchmark` is a
  symlink. Git for Windows checks it out as a small text file unless
  symlinks are enabled. Read `skills/caml-benchmark/` directly, or install
  the plugin (`/plugin marketplace add A1i-Tabatabaei/CAML`).

## WSL

- Use [operator-linux.md](operator-linux.md). WSL is a Linux shell.
- WSL has its own `~/.ssh`, separate from `C:\Users\NAME\.ssh`. Either set
  up a key inside WSL, or copy the Windows one:
  `cp -r /mnt/c/Users/NAME/.ssh ~/ && chmod 700 ~/.ssh && chmod 600 ~/.ssh/*`.
- Windows files are under `/mnt/c/Users/NAME/...`.
