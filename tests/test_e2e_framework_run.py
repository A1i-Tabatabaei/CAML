"""End-to-end tests: for every framework that is actually installed in this
checkout, run it for real against ``resources/benchmarks/test.yaml``'s three
tiny tasks (kc2 binary, iris multiclass, cholesterol regression; 2 folds
each under the ``test`` constraint) and assert every job produced a real,
non-NaN score. This is the manual "smoke test" step of
``docs/operations/vps-runbook.md`` (step 3), codified so it can't be skipped
or eyeballed loosely.

Per CLAUDE.md's local-vs-VPS policy, no framework is ever installed on the
local dev machine, so this file collects zero live cases there --
``pytest.mark.parametrize`` over an empty list is reported as a single
skipped test (pytest's standard behavior), not a failure. It only becomes
meaningful where frameworks are actually installed: the VPS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caml.frameworks.installer import is_installed
from caml.frameworks.registry import discover_frameworks

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORKS_ROOT = REPO_ROOT / "frameworks"


def _installed_frameworks():
    definitions = discover_frameworks(FRAMEWORKS_ROOT)
    return [
        fw
        for fw in definitions.values()
        if is_installed(fw.manifest.dir, fw.manifest)
    ]


@pytest.mark.parametrize(
    "fw", _installed_frameworks(), ids=lambda fw: fw.name
)
def test_framework_smoke_e2e(fw):
    # Imported lazily: importing caml.benchmark eagerly at collection time
    # would make every *unrelated* test file pay its import cost even when
    # no framework is installed and this test is about to be skipped.
    from caml.benchmark import Benchmark, SetupMode
    from caml.cli import _bootstrap_resources

    _bootstrap_resources(REPO_ROOT)
    bench = Benchmark(fw.name, "test", "test")
    bench.setup(SetupMode.auto)  # no-op: fw is already installed
    scores = bench.run()

    assert not scores.empty, f"{fw.name}: benchmark produced no jobs at all"

    failed = scores[scores["result"].isna()]
    assert failed.empty, (
        f"{fw.name}: {len(failed)}/{len(scores)} job(s) produced no score "
        f"(NaN result):\n{failed[['task', 'fold', 'info']].to_string(index=False)}"
    )
