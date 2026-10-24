# TabPFN (Prior Labs) API access

**This page intentionally contains no real API key.** Like VPS credentials
(see `vps-access.md`), the real value must never be committed to this repo,
in this file or any other — not even temporarily.

## Where the real key actually lives

- An untracked local note: `docs/operations/.tabpfn-access.local.md`
  (already `.gitignore`d — see the repo's `.gitignore`), or
- Directly as an exported environment variable in the `caml` user's shell
  profile on the VPS (`~caml/.bashrc` or similar) — this is the mechanism
  that actually matters at runtime. **Both TabPFN frameworks read
  `TABPFN_TOKEN` straight from the process environment** (CAML doesn't parse
  or forward it from a file): the hosted `TabPFNClient` (`tabpfn-client`) uses
  it on *every* call, and the local `TabPFN` (`tabpfn`) uses it *once*, to
  authorize the one-time model-weight download.

Both frameworks' `__init__.py` explicitly retain `TABPFN_TOKEN` across the
subprocess boundary (`run_in_venv`'s default `retained_env_vars` is just
`TMP`/`TEMP`/`TMPDIR`; the local `TabPFN` also retains
`TABPFN_MODEL_CACHE_DIR`), and each `exec.py` fails fast with a clear error if
the variable is unset or still equal to the placeholder below — so a missing
token shows up as an obvious, actionable message rather than a confusing
failure deep inside the underlying package.

## What's committed instead

Both frameworks' `exec.py` hardcode one recognizable placeholder string
so anyone reading the tracked code (here, or on GitHub) immediately sees
that a real key is expected and where:

```
TABPFN_TOKEN=REPLACE_WITH_YOUR_TABPFN_API_KEY
```

## Getting a real key

1. Register at <https://ux.priorlabs.ai>.
2. Accept the licenses under the account's Licenses tab. **For the local
   `TabPFN` framework, the TabPFN-3 model license (`tabpfn-3-license-v1.0`)
   must be accepted** or the weight download fails with a
   `TabPFNLicenseError` on the headless box (the token alone is not enough).
   Accepting all offered licenses (TabPFN-3/2.6/2.5) is simplest and also
   covers the hosted `TabPFNClient`.
3. Copy an API key from the account page.
4. Set it as `TABPFN_TOKEN` in the `caml` user's VPS shell environment
   (and record it in `.tabpfn-access.local.md` for reference) before
   running `caml install TabPFN` (local) or `caml install TabPFNClient`
   (hosted) and the matching `caml run …`.

If you're a coding agent picking up TabPFN work: ask the user for the
token each session (or confirm the untracked local note / VPS environment
variable is already set) rather than expecting it to be recorded anywhere
in git history.
