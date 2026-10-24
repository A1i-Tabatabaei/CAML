# Framework plugin contract

This is the authoritative reference for `framework.toml` — also the
practical "how do I add framework #12" doc (see
`contributing/adding-a-framework.md` for the step-by-step recipe; this page
is the schema reference it points back to).

## Why this exists

AMLB integrates each framework via a hand-rolled `setup.sh` that mixes venv
creation, pip invocation, and version-marker bookkeeping, with only
cosmetic differences between the 20+ copies of this pattern in its
`frameworks/` tree. AMLB's own maintainers flagged this as a maintenance
burden — see issues
[#64](https://github.com/openml/automlbenchmark/issues/64) ("simplify
install + standardize venv usage") and
[#642](https://github.com/openml/automlbenchmark/issues/642) ("defaults to
improve framework integration setup"). CAML replaces all of that with:

1. **One declarative manifest per framework**, `frameworks/<Name>/framework.toml`.
2. **One shared installer**, `src/caml/frameworks/installer.py`, that does
   the actual work. A manifest only ever declares *what* differs between
   frameworks; the installer is the only place that knows *how* to turn
   that into a working isolated environment.

## `framework.toml` schema

```toml
[framework]
name = "FLAML"            # must match the directory name
tier = 1                  # 1 or 2, see STATUS.md roster
project_url = "https://github.com/microsoft/FLAML"
license = "MIT"

[python]
range = ">=3.11,<3.13"    # a range; installer.py resolves it to a concrete
                          # CPython minor version via packaging.SpecifierSet
                          # against _CANDIDATE_PYTHONS, then `uv python install`s it

[install]
packages = ["flaml[automl]==2.6.0"]   # exact-pinned, see version-pinning-policy.md
extra_index_urls = []                  # e.g. CPU-only torch index for LightAutoML/TabPFN
post_install_script = ""               # rare escape hatch, e.g. TabPFN's HF weight pre-warm

[install.system_packages]
apt = []                  # e.g. ["openjdk-17-jre-headless"] for H2OAutoML

[version_check]
pypi_package = "flaml"    # PyPI project name, used by `caml check-versions`
current_pin = "2.6.0"     # single source of truth for "what CAML is pinned to"

[exec]
entrypoint = "exec.py"    # relative to the framework's own directory

[notes]
last_verified = "2026-07-17"
gotchas = "free text — anything the next person touching this framework should know"
```

TOML was chosen over YAML deliberately: stdlib `tomllib` (Python ≥3.11,
zero extra dependency), and it avoids the indentation-sensitivity that
already causes subtle bugs in AMLB's own `frameworks.yaml` `params` blocks.
A full per-framework `pyproject.toml` was considered and rejected — it
would imply each framework directory is an independently
buildable/publishable package, which it isn't; `framework.toml` is a
config manifest, not a build spec.

## What `installer.py` does with a manifest

1. Load + validate (`src/caml/frameworks/manifest.py`, pydantic) — fails
   loudly with a field-level error on a malformed manifest, rather than
   AMLB's silent/late failures from a malformed `frameworks.yaml` entry.
2. Resolve `[python].range` to a concrete CPython version.
3. `uv python install <version>` (idempotent).
4. `uv venv frameworks/<Name>/venv --python <version>` — if
   `.setup/installed` already matches the manifest's pin + Python version,
   this is a no-op; on any mismatch the venv is deleted and rebuilt from
   scratch rather than patched in place.
5. Ensure `[install.system_packages].apt` are present (`dpkg -s` guard,
   installs only what's missing).
6. `uv pip install` the shared baseline (`frameworks/shared/requirements.txt`)
   then the framework's own `[install].packages`, honoring
   `extra_index_urls`.
7. Run `post_install_script` if declared.
8. Write `.setup/installed` as structured JSON (framework, pinned_version,
   installed_version, python, uv_version, installed_at) — this is what
   `caml status` reads.

## The `run()` side is unchanged

`framework.toml` only touches *installation*. Running a framework still
goes through `frameworks/<Name>/__init__.py::run()` →
`frameworks.shared.caller.run_in_venv()` → `exec.py` inside the venv — see
`overview.md` for that half of the picture.
