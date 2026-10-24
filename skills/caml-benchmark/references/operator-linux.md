# Operator profile: Linux (and WSL)

You, the agent, run on the user's Linux machine, or in WSL on Windows. CAML
runs on their Ubuntu 24.04 server. This machine only sends commands over
SSH, copies files with `scp`, and keeps the reports. **Install nothing on
it**: no Python packages, no uv, no AutoML frameworks. They are tens of GB,
and the benchmark's timings only mean something on the server.

Everything on the server goes through `ssh caml-vps camlctl ...`
([camlctl.md](camlctl.md)).

## 1. Confirm where you are

```bash
uname -sr
grep PRETTY_NAME /etc/os-release
grep -qi microsoft /proc/version && echo WSL
```

Write the distribution, kernel, shell (`echo $SHELL`) and `ssh -V` into the
field report's Environment section before you start.

**Are you on the CAML server itself?** If `hostname` matches the server and
`/usr/local/bin/camlctl` exists, skip SSH: run `camlctl ...` directly as
root, or `sudo camlctl ...`.

## 2. SSH access

Check it. This must print `ok` without asking for anything:

```bash
ssh -o BatchMode=yes caml-vps echo ok
```

If it fails, the user sets it up once. They run these themselves; the copy
step asks for the server's root password, which never goes through you.

1. A key (press Enter at each question): `ssh-keygen -t ed25519`
2. Copy it: `ssh-copy-id root@SERVER_IP`
3. If the key has a passphrase: `ssh-add ~/.ssh/id_ed25519` in the session
   the agent runs in (or use the desktop's keyring agent).
4. Add the host alias to `~/.ssh/config`:

   ```text
   Host caml-vps
     HostName SERVER_IP
     User root
     IdentityFile ~/.ssh/id_ed25519
     ServerAliveInterval 30
     ServerAliveCountMax 6
   ```

   If the file came from a Mac and contains `UseKeychain`, add
   `IgnoreUnknown UseKeychain` as its first line. Otherwise ssh rejects it
   (`Bad configuration option: usekeychain`).

**WSL**: WSL's `~/.ssh` is separate from Windows' `C:\Users\NAME\.ssh`. Set
up a key inside WSL, or copy the Windows one:
`cp -r /mnt/c/Users/NAME/.ssh ~/ && chmod 700 ~/.ssh && chmod 600 ~/.ssh/*`.
Windows files are under `/mnt/c/Users/NAME/...`.

## 3. The quoting rule

- Server work: `ssh caml-vps camlctl COMMAND plain words`.
- A raw shell command on the server (only setup's first two steps need one):
  one pair of double quotes, with no `$`, backtick, `%`, `!` or `"` inside.
  Your shell would expand `$` locally, and the rule keeps every doc command
  valid on Windows too.
- Anything longer: write a script, `scp` it over, and run
  `ssh caml-vps camlctl script NAME.sh`.
- Server file names: simple words only. Rename on upload:
  `scp "/path/My Data.csv" caml-vps:churn.csv`.

## 4. Local commands

| Task | Command |
|---|---|
| File size | `ls -lh "/path/data.csv"` |
| First lines | `head -n 5 "/path/data.csv"` |
| Encoding hint | `file -i "/path/data.csv"` (`camlctl dataset` checks it properly on the server) |
| SHA-256 | `sha256sum "/path/data.csv"` |
| Upload | `scp "/path/My Data.csv" caml-vps:churn.csv` |
| Report folder | `mkdir -p ~/caml-run` |
| Download a bundle | `scp caml-vps:caml-bundles/NAME.tar.gz ~/caml-run/` |
| Unpack it | `tar -xzf ~/caml-run/NAME.tar.gz -C ~/caml-run` |
| Pause | `sleep 60` |
| Stay awake while you monitor | `systemd-inhibit --what=sleep --why="CAML monitoring" sleep 6h` in the background |

## 5. Gotchas

- **Your tool's timeout.** Agent shell tools often stop a command after
  2–10 minutes. Never run setup, installs or sweeps in the foreground: use
  `camlctl start`, then `camlctl wait JOB SECONDS` with SECONDS below your
  tool's limit.
- **Sleep.** A detached job keeps running on the server whatever this
  machine does; only your monitoring pauses.
- **The TabPFN key** needs a real terminal. The user runs
  `ssh -t caml-vps camlctl tabpfn-token` themselves, not through your shell
  tool.
- **Spreadsheet exports.** LibreOffice: File > Save As > Text CSV, with
  "Character set: Unicode (UTF-8)". A Windows Excel "CSV (Comma
  delimited)" file is Windows-1252: convert it on the server with
  `camlctl dataset FILE --from-encoding WINDOWS-1252`.

## Developers: provisioning from a clone

From a clone, `scripts/provision_vps.sh caml-vps` packages the checked-out
commit and provisions the server without GitHub access on the server.
`INCLUDE_WORKTREE=1` packages uncommitted changes too, and
`scripts/sync_vps.sh caml-vps` pushes later changes. For users,
`camlctl setup` (clone on the server) is simpler.
