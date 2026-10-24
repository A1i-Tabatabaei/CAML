# Operator profile: macOS

You, the agent, run on the user's Mac. CAML runs on their Ubuntu 24.04
server. This Mac only sends commands over SSH, copies files with `scp`, and
keeps the reports. **Install nothing on it**: no Homebrew packages, no
Python packages, no uv, no AutoML frameworks, no converters.

Everything on the server goes through `ssh caml-vps camlctl ...`
([camlctl.md](camlctl.md)).

## 1. Confirm where you are

```bash
uname -s
sw_vers
echo $SHELL
```

`uname -s` prints `Darwin`. `sw_vers` gives the macOS version, and the shell
is zsh by default. Write these, plus `uname -m` (`arm64` or `x86_64`) and
`ssh -V`, into the field report's Environment section before you start.

## 2. SSH access

Check it. This must print `ok` without asking for anything:

```bash
ssh -o BatchMode=yes caml-vps echo ok
```

If it fails, the user sets it up once. They run these themselves; the copy
step asks for the server's root password, which never goes through you.

1. A key (press Enter at each question): `ssh-keygen -t ed25519`
2. Copy it to the server: `ssh-copy-id root@SERVER_IP`. If macOS says
   `command not found`, use:
   `cat ~/.ssh/id_ed25519.pub | ssh root@SERVER_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"`
3. If the key has a passphrase, store it in the keychain once, so your
   non-interactive `ssh` never stops at a prompt:
   `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`
4. Add the host alias to `~/.ssh/config`, for example with
   `nano ~/.ssh/config`:

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

   `UseKeychain` exists only on macOS. If this config file is shared with
   Linux machines (dotfiles), put `IgnoreUnknown UseKeychain` on the first
   line, or Linux ssh refuses the whole file
   (`Bad configuration option: usekeychain`).

## 3. The quoting rule

- Server work: `ssh caml-vps camlctl COMMAND plain words`.
- A raw shell command on the server (only setup's first two steps need one):
  one pair of double quotes, with no `$`, backtick, `%`, `!` or `"` inside.
  zsh would expand `$` and backticks locally. The same rule keeps every doc
  command valid on Windows too.
- Anything longer: write a script, `scp` it over, and run
  `ssh caml-vps camlctl script NAME.sh`.
- Server file names: simple words only. Rename on upload:
  `scp "/Users/me/Downloads/My Data (final).csv" caml-vps:churn.csv`.

## 4. Local commands

| Task | Command |
|---|---|
| File size | `ls -lh "/path/data.csv"` |
| Header line (column names only: don't print data rows) | `head -n 1 "/path/data.csv"` |
| Encoding hint | `file -I "/path/data.csv"` (`camlctl dataset` checks it properly on the server) |
| SHA-256 | `shasum -a 256 "/path/data.csv"` |
| Upload | `scp "/path/My Data.csv" caml-vps:churn.csv` |
| Report folder | `mkdir -p ~/caml-run` |
| Download a bundle | `scp caml-vps:caml-bundles/NAME.tar.gz ~/caml-run/` |
| Unpack it | `tar -xzf ~/caml-run/NAME.tar.gz -C ~/caml-run` |
| Pause | `sleep 60` |
| Keys file: create | Your file tool, at `~/caml-run/caml-secrets.env`, from `ssh caml-vps camlctl secrets --template` |
| Keys file: open it for the user | `open -e ~/caml-run/caml-secrets.env` (TextEdit) |
| Keys file: upload, then delete | `scp ~/caml-run/caml-secrets.env caml-vps:caml-secrets.env`, then `rm ~/caml-run/caml-secrets.env` |
| Stay awake while you monitor | `caffeinate -i -t 21600` in the background (6 hours), or ask the user to keep the Mac plugged in |

## 5. Gotchas

- **BSD tools, not GNU.** There's no `timeout` or `watch`, and `sha256sum`
  may be missing (`shasum -a 256` works on every macOS). `sed -i` needs an
  empty suffix argument (`sed -i ''`). `date -d` and `mktemp --suffix` don't
  exist. Keep Mac-side commands simple: the real work runs on the server,
  which has GNU tools.
- **`/bin/bash` is 3.2.** No `mapfile`, and an empty array under `set -u`
  fails with "unbound variable". Your shell tool probably runs zsh anyway.
- **zsh and `#`.** Interactive zsh doesn't treat `#` as a comment unless
  `INTERACTIVE_COMMENTS` is set. Give the user commands to paste without
  comments, one command per block.
- **git can open an installer.** The first `git` on a fresh Mac pops up the
  Command Line Tools installer. Tell the user and wait, or read the repo on
  GitHub instead of cloning it.
- **`._` files.** macOS tar adds AppleDouble `._name` files unless
  `COPYFILE_DISABLE=1` is set. CAML's `provision_vps.sh` sets it. Do the
  same if you ever tar files for the server.
- **Spreadsheet exports.** Excel: File > Save As > **CSV UTF-8**. Numbers:
  File > Export To > CSV, with the text encoding set to Unicode (UTF-8).
  Older "CSV (Macintosh)" exports are Mac Roman: on the server, convert with
  `camlctl dataset FILE --from-encoding MACINTOSH`. `.xlsx` and `.numbers`
  files don't load.
- **iCloud Drive.** With "Optimize Mac Storage" on, a file in Desktop,
  Documents or iCloud Drive may not be on disk (a cloud icon in Finder).
  Ask the user to download it first.
- **Sleep.** A detached job keeps running on the server; only your
  monitoring pauses while the Mac sleeps. Closing the lid sleeps the Mac
  even with `caffeinate` running, unless it's on power with an external
  display.
- **API keys** need a real terminal. The user runs
  `ssh -t caml-vps camlctl secrets` in Terminal themselves, not through your
  shell tool ([checkpoints.md](checkpoints.md) §2). If they'd rather fill in
  `caml-secrets.env`, TextEdit opens it as plain text. Tell them not to type
  quotes: TextEdit's smart quotes turn them into curly ones (the import
  strips both kinds, but it's one less thing to go wrong).

## Developers: provisioning from a clone

From a clone, `scripts/provision_vps.sh caml-vps` packages the checked-out
commit and provisions the server without GitHub access on the server. Since
1.0.1 it works on macOS (the stock bash 3.2, BSD `mktemp` and `bsdtar`).
`scripts/sync_vps.sh caml-vps` pushes later code changes. For users,
`camlctl setup` (clone on the server) is simpler.
