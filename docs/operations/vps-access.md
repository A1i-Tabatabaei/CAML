# VPS access

**This page intentionally contains no real host, IP, username, or
credential.** VPS connection details must never be committed to this repo,
in this file or any other — not even temporarily.

## Where connection details actually live

- An SSH config entry (`~/.ssh/config`) on the machine doing the work, or
- An untracked local note, e.g. `docs/operations/.vps-access.local.md`
  (already `.gitignore`d — see the repo's `.gitignore`).

If you're a coding agent picking up VPS work: ask the user for connection
details each session (or confirm the untracked local note still exists and
is current) rather than expecting them to be recorded anywhere in git
history.

## What to record here instead

Non-sensitive operational facts that *are* safe to commit:

- VPS provider/region (if relevant to troubleshooting, e.g. a
  provider-specific apt mirror quirk).
- Confirmed specs (disk/RAM/cores) once known — cross-check against the
  ≥50GB disk / ≥8GB RAM recommendation in `getting-started/vps-bootstrap.md`.
- Date bootstrap was last run and by whom/what session.

(Nothing recorded yet — fill in once the VPS is handed over.)
