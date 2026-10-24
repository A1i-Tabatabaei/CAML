# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for a security problem. Use GitHub's
private reporting instead: the repository's **Security** tab, then
**Report a vulnerability**. Include what is affected, how to reproduce it,
and the impact you expect. You should get a reply within a week.

## What's in scope

- The provisioning scripts in `scripts/`. `bootstrap_vps.sh` runs as root,
  creates the `caml` user, and adds a sudoers entry that lets it run only
  `apt-get install -y *`.
- How CAML handles secrets: `TABPFN_TOKEN` is read from the environment and
  passed only to the two TabPFN framework subprocesses.
- Code that downloads data or packages: OpenML datasets, PyPI, the PyTorch
  wheel index.

The AutoML frameworks themselves are separate projects. Report their
vulnerabilities upstream.

## Running CAML safely

- Use a disposable server dedicated to benchmarking, not one that holds
  other data or credentials.
- Keep tokens out of the repository and out of shell history (see the
  README's TabPFN section). Revoke any token that leaks.
- `TabPFNClient` uploads training and test data to Prior Labs' API. Don't run
  it on data you aren't allowed to share.
