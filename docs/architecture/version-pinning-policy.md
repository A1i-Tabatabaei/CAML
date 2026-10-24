# Version pinning policy

**CAML exact-pins every framework, and bumps deliberately.** This is a
direct rejection of AMLB's default behavior, and the reasoning matters
enough to spell out.

## What AMLB does today

Most of AMLB's framework definitions set `version: "stable"`, which its
`setup.sh` resolves to `pip install -U <package>` — whatever is newest on
PyPI *at install time*. There's no lockfile and no reproducibility: running
setup today and running it again in three months can silently install
different versions.

## Why that's a real problem, not a theoretical one

TPOT shipped a ground-up rewrite in 2025 (v1.x) that removed the
`config_dict=` constructor argument AMLB's `TPOT/exec.py` passes, and
renamed the fitted-individuals attribute from `evaluated_individuals_`
(dict) to `evaluated_individuals` (DataFrame). Because AMLB pins TPOT to
`"stable"`, this breaking change landed silently — anyone running
`python runbenchmark.py TPOT ...` today gets a crash, with no signal from
AMLB's own config that anything changed. The always-latest default is
*how* a breaking upstream rewrite becomes a silent breakage in a benchmark
tool whose entire value proposition is comparing frameworks under known,
reproducible conditions.

## CAML's policy

- Each framework's `framework.toml` → `[version_check].current_pin` is set
  to whatever is genuinely latest **when that framework is brought
  online** (not copied forward from AMLB's old pins — every framework in
  CAML starts current, then holds still deliberately).
- The default install path (`caml install <name>`) always installs the pin.
- `caml install <name> --latest` is an explicit, one-off escape hatch: it
  strips the version pin from the package spec and lets `uv pip install`
  resolve whatever PyPI serves right now, without touching
  `current_pin`. Useful for "does the new release fix bug X" investigation.
- Whichever version actually got installed is recorded both in
  `.setup/installed` (structured JSON) and in the benchmark run's result
  metadata — so a result row always says exactly which framework version
  produced it, regardless of which install path was used.
- **FEDOT deviation**: AMLB's `resources/frameworks.yaml` pins FEDOT to git
  `master` (not a PyPI release) — maximally non-reproducible, since
  upstream can change the integration's behavior with no CAML-side commit
  at all. CAML pins FEDOT to its latest PyPI release instead, like every
  other framework.

## Keeping pins current

`caml check-versions` (a real v1 command, not backlog) does a PyPI JSON API
GET per framework and reports whether `current_pin` matches the latest
release. Bumping a pin is a deliberate, reviewed action: update
`current_pin` in the framework's `framework.toml`, re-verify on the VPS
(see `operations/vps-runbook.md`), update `last_verified` in `[notes]`.

An automated "bot opens an issue when a new upstream release drops" is
explicitly **backlog** (`STATUS.md` Phase 8), not v1 — flagged rather than
silently built, since it's a real scope decision the user should weigh in
on.
