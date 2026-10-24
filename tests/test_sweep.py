"""Tests for caml.sweep: matrix/shard/resume/classification logic, the
run_sweep() bookkeeping loop (with an injected fake runner, so no framework
runs), real-subprocess timeout/kill behaviour of run_job(), and the CLI
wiring (`caml sweep --dry-run`, `caml run --seed/--keep-going`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from caml import sweep
from caml.sweep import SweepJob, TaskSpec

RESULT_COLUMNS = ["framework", "task", "constraint", "fold", "result", "metric", "version", "app_version", "info"]


# --- matrix / shard ---------------------------------------------------------

def test_build_matrix_is_fold_major_and_respects_per_task_folds():
    tasks = [TaskSpec("a", 2, 60), TaskSpec("b", 1, 120)]
    jobs = sweep.build_matrix(["F1", "F2"], tasks)
    assert [(j.fold, j.task, j.framework) for j in jobs] == [
        (0, "a", "F1"), (0, "a", "F2"), (0, "b", "F1"), (0, "b", "F2"),
        (1, "a", "F1"), (1, "a", "F2"),          # b has only 1 fold
    ]
    assert jobs[2].max_runtime_seconds == 120


def test_build_matrix_fold_filter():
    jobs = sweep.build_matrix(["F"], [TaskSpec("a", 3, 60)], folds=[2])
    assert [j.fold for j in jobs] == [2]


def test_build_matrix_empty():
    assert sweep.build_matrix(["F"], []) == []


@pytest.mark.parametrize("spec,expected", [("1/1", (1, 1)), ("2/4", (2, 4)), (" 3 / 3 ", (3, 3))])
def test_parse_shard_valid(spec, expected):
    assert sweep.parse_shard(spec) == expected


@pytest.mark.parametrize("spec", ["", "0/2", "3/2", "1/0", "a/b", "2"])
def test_parse_shard_invalid(spec):
    with pytest.raises(ValueError):
        sweep.parse_shard(spec)


def test_shards_partition_the_matrix():
    jobs = sweep.build_matrix(["F1", "F2", "F3"], [TaskSpec(f"t{i}", 3, 60) for i in range(4)])
    shards = [sweep.select_shard(jobs, k, 3) for k in (1, 2, 3)]
    flat = [j for s in shards for j in s]
    assert sorted(flat, key=lambda j: j.key) == sorted(jobs, key=lambda j: j.key)
    assert len(set(j.key for j in flat)) == len(jobs)
    assert max(len(s) for s in shards) - min(len(s) for s in shards) <= 1


def test_hard_timeout():
    job = SweepJob("F", "t", 0, 600)
    assert sweep.hard_timeout_secs(job) == 2 * 600 + sweep.HARD_TIMEOUT_MARGIN_SECS
    assert sweep.hard_timeout_secs(job, override=5) == 5


def test_log_name_sanitizes_task():
    assert SweepJob("F", "openml/t/59 x", 1, 60).log_name == "F.openml-t-59-x.1.log"


# --- ledger / resume --------------------------------------------------------

def test_ledger_latest_wins_and_tolerates_torn_line(tmp_path):
    ledger = sweep.Ledger(tmp_path / "ledger.jsonl")
    ledger.append({"framework": "F", "task": "t", "fold": 0, "status": "crash"})
    ledger.append({"framework": "F", "task": "t", "fold": 0, "status": "ok"})
    with ledger.path.open("a") as f:
        f.write('{"framework": "F", "task": "u", "fo')   # hard kill mid-write
    latest = ledger.latest()
    assert latest == {("F", "t", 0): {"framework": "F", "task": "t", "fold": 0, "status": "ok"}}


def test_pending_jobs():
    jobs = [SweepJob("F", t, 0, 60) for t in ("ok", "bad", "new")]
    latest = {("F", "ok", 0): {"status": "ok"}, ("F", "bad", 0): {"status": "crash"}}
    assert [j.task for j in sweep.pending_jobs(jobs, latest)] == ["new"]
    assert [j.task for j in sweep.pending_jobs(jobs, latest, retry_failed=True)] == ["bad", "new"]


# --- classification ---------------------------------------------------------

def _rows(*results, info=None):
    return pd.DataFrame({"result": list(results), "info": [info] * len(results)})


EMPTY = pd.DataFrame(columns=["result", "info"])


@pytest.mark.parametrize("returncode,timed_out,rows,status", [
    (0, False, _rows(0.9), "ok"),
    (None, True, _rows(0.9), "ok"),                    # row landed just before the kill
    (1, False, _rows(float("nan"), info="ValueError: boom"), "error"),
    (None, True, EMPTY, "timeout"),
    (-9, False, EMPTY, "killed"),
    (137, False, EMPTY, "killed"),
    (1, False, EMPTY, "crash"),
    (0, False, EMPTY, "no_result"),
])
def test_classify(returncode, timed_out, rows, status):
    assert sweep.classify(returncode, timed_out, rows)[0] == status


def test_classify_error_carries_info():
    assert sweep.classify(1, False, _rows(float("nan"), info="ValueError: boom")) == ("error", "ValueError: boom")


def test_classify_killed_names_signal():
    assert "SIGKILL" in sweep.classify(-9, False, EMPTY)[1]


def test_tail_line(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("first\nTraceback\nRuntimeError: real cause\n\n")
    assert sweep.tail_line(p) == "RuntimeError: real cause"
    assert sweep.tail_line(tmp_path / "missing.log") == ""


# --- run_sweep with a fake runner ---------------------------------------------

class FakeRunner:
    """Pretends to be `caml run`: appends a results.csv row per scripted
    outcome, like the real CLI's global-scoreboard save does."""

    def __init__(self, results_csv: Path, outcomes: dict):
        self.results_csv = results_csv
        self.outcomes = outcomes   # task -> "ok" | "error" | "crash" | "timeout"
        self.calls = []

    def __call__(self, cmd, log_path, timeout):
        self.calls.append(cmd)
        fw, task, fold = cmd[2], cmd[cmd.index("--task") + 1], int(cmd[cmd.index("--fold") + 1])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        outcome = self.outcomes[task]
        if outcome in ("ok", "error"):
            row = {"framework": fw, "task": task, "constraint": "c", "fold": fold,
                   "result": 0.8 if outcome == "ok" else float("nan"), "metric": "auc",
                   "version": "1.2.3", "app_version": "dev [main, abc1234]",
                   "info": None if outcome == "ok" else "RuntimeError: nope"}
            df = pd.DataFrame([row], columns=RESULT_COLUMNS)
            df.to_csv(self.results_csv, mode="a", header=not self.results_csv.exists(), index=False)
        log_path.write_text(f"running {task}\nFatalError: {task} died\n")
        if outcome == "crash":
            return 1, False, 0.1
        if outcome == "timeout":
            return None, True, 0.1
        return (0 if outcome == "ok" else 0), False, 0.1


def _run(tmp_path, jobs, runner, **kwargs):
    return sweep.run_sweep(
        jobs, sweep_dir=tmp_path / "sweep", results_csv=tmp_path / "results.csv",
        benchmark="b", constraint="c", seed=7, caml_exe="caml", app_version="dev [x, y]",
        echo=lambda _msg: None, runner=runner, **kwargs,
    )


def test_run_sweep_classifies_records_and_resumes(tmp_path):
    jobs = sweep.build_matrix(["F"], [TaskSpec(t, 1, 60) for t in ("good", "bad", "boom", "hang")])
    runner = FakeRunner(tmp_path / "results.csv", {"good": "ok", "bad": "error", "boom": "crash", "hang": "timeout"})
    summary = _run(tmp_path, jobs, runner)

    latest = sweep.Ledger(tmp_path / "sweep" / "ledger.jsonl").latest()
    status = {k[1]: v["status"] for k, v in latest.items()}
    assert status == {"good": "ok", "bad": "error", "boom": "crash", "hang": "timeout"}
    good = latest[("F", "good", 0)]
    assert good["result"] == 0.8 and good["framework_version"] == "1.2.3"
    assert good["app_version"] == "dev [main, abc1234]" and good["seed"] == 7
    assert latest[("F", "bad", 0)]["detail"] == "RuntimeError: nope"
    assert "FatalError: boom died" in latest[("F", "boom", 0)]["detail"]
    assert summary["per_framework"]["F"]["ok"] == 1 and not summary["interrupted"]

    # The job command carries the reproducibility/isolation flags.
    first = runner.calls[0]
    assert first[first.index("--seed") + 1] == "7" and "--keep-going" in first

    # Resume: nothing left to do.
    runner.calls.clear()
    _run(tmp_path, jobs, runner)
    assert runner.calls == []

    # --retry-failed re-runs only the three failures; the latest record wins.
    runner.outcomes.update({"bad": "ok", "boom": "ok", "hang": "ok"})
    _run(tmp_path, jobs, runner, retry_failed=True)
    assert sorted(c[c.index("--task") + 1] for c in runner.calls) == ["bad", "boom", "hang"]
    latest = sweep.Ledger(tmp_path / "sweep" / "ledger.jsonl").latest()
    assert {v["status"] for v in latest.values()} == {"ok"}


def test_run_sweep_ignores_preexisting_rows_for_same_job(tmp_path):
    """An older results.csv row for the same (fw, task, fold) must not make a
    crashed re-run look like a success."""
    results = tmp_path / "results.csv"
    pd.DataFrame([{"framework": "F", "task": "t", "constraint": "c", "fold": 0, "result": 0.9,
                   "metric": "auc", "version": "1", "app_version": "old", "info": None}],
                 columns=RESULT_COLUMNS).to_csv(results, index=False)
    jobs = sweep.build_matrix(["F"], [TaskSpec("t", 1, 60)])
    _run(tmp_path, jobs, FakeRunner(results, {"t": "crash"}))
    assert sweep.Ledger(tmp_path / "sweep" / "ledger.jsonl").latest()[("F", "t", 0)]["status"] == "crash"


def test_run_sweep_max_jobs(tmp_path):
    jobs = sweep.build_matrix(["F"], [TaskSpec(t, 1, 60) for t in ("a", "b", "c")])
    runner = FakeRunner(tmp_path / "results.csv", {"a": "ok", "b": "ok", "c": "ok"})
    summary = _run(tmp_path, jobs, runner, max_jobs=2)
    assert len(runner.calls) == 2 and summary["per_framework"]["F"]["pending"] == 1


def test_run_sweep_refuses_concurrent_driver(tmp_path):
    with sweep.SweepLock(tmp_path / "sweep"):
        with pytest.raises(sweep.SweepLockedError):
            _run(tmp_path, sweep.build_matrix(["F"], [TaskSpec("a", 1, 60)]), FakeRunner(tmp_path / "r.csv", {"a": "ok"}))


def test_run_sweep_interrupt_leaves_job_unrecorded(tmp_path):
    def interrupted_runner(cmd, log_path, timeout):
        raise sweep._Interrupted(2)

    summary = _run(tmp_path, sweep.build_matrix(["F"], [TaskSpec("a", 1, 60)]), interrupted_runner)
    assert summary["interrupted"]
    assert sweep.Ledger(tmp_path / "sweep" / "ledger.jsonl").latest() == {}


def test_format_summary():
    jobs = sweep.build_matrix(["F"], [TaskSpec("a", 2, 60)])
    text = sweep.format_summary(sweep.summarize(jobs, {("F", "a", 0): {"status": "ok"}}))
    assert "PENDING" in text.splitlines()[0]
    assert text.splitlines()[1].split()[:3] == ["F", "1", "1"]


# --- run_job against real subprocesses -----------------------------------------

def test_run_job_returncode_and_log(tmp_path):
    log = tmp_path / "logs" / "j.log"
    rc, timed_out, _ = sweep.run_job(["sh", "-c", "echo hello; exit 3"], log, timeout_secs=30)
    assert (rc, timed_out) == (3, False)
    assert log.read_text().strip() == "hello"


def test_run_job_timeout_kills_whole_process_group(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep, "_TERM_GRACE_SECS", 2)
    marker = tmp_path / "child.pid"
    # The shell backgrounds a grandchild and records its pid, then hangs.
    script = f"sleep 60 & echo $! > {marker}; wait"
    start = time.monotonic()
    rc, timed_out, wall = sweep.run_job(["sh", "-c", script], tmp_path / "j.log", timeout_secs=1)
    assert timed_out and time.monotonic() - start < 15
    child = int(marker.read_text())
    time.sleep(0.2)
    alive = subprocess.run(["ps", "-p", str(child), "-o", "stat="], capture_output=True, text=True).stdout.strip()
    assert alive == "" or alive.startswith("Z"), f"grandchild {child} survived the job kill"


def test_run_job_reaps_stray_children_after_normal_exit(tmp_path):
    marker = tmp_path / "child.pid"
    sweep.run_job(["sh", "-c", f"sleep 60 & echo $! > {marker}; exit 0"], tmp_path / "j.log", timeout_secs=30)
    child = int(marker.read_text())
    time.sleep(0.2)
    alive = subprocess.run(["ps", "-p", str(child), "-o", "stat="], capture_output=True, text=True).stdout.strip()
    assert alive == "" or alive.startswith("Z"), f"stray child {child} outlived its job"


# --- CLI wiring ------------------------------------------------------------------

def test_cli_run_exposes_seed_and_keep_going():
    from caml.cli import main
    out = CliRunner().invoke(main, ["run", "--help"]).output
    assert "--seed" in out and "--keep-going" in out


def test_cli_sweep_dry_run_lists_test_benchmark_matrix():
    from caml.cli import main
    res = CliRunner().invoke(main, ["sweep", "FLAML", "GAMA", "--benchmark", "test", "--constraint", "test",
                                    "--name", "pytest-dry-run", "--dry-run"])
    assert res.exit_code == 0, res.output
    lines = [ln for ln in res.output.splitlines() if "fold" in ln]
    assert len(lines) == 3 * 2 * 2      # 3 tasks x 2 folds x 2 frameworks
    assert lines[0].split()[:2] == ["FLAML", "kc2"] and lines[1].split()[:2] == ["GAMA", "kc2"]


def test_cli_sweep_rejects_bad_shard():
    from caml.cli import main
    res = CliRunner().invoke(main, ["sweep", "FLAML", "--benchmark", "test", "--constraint", "test", "--shard", "5/2"])
    assert res.exit_code != 0 and "shard" in res.output.lower()


# --- REVISION fallback (VPS checkouts have no .git) ------------------------------

def test_app_version_falls_back_to_revision_file(tmp_path, monkeypatch):
    from caml import resources
    from caml.cli import _bootstrap_resources
    from caml.paths import find_repo_root

    (tmp_path / "resources").mkdir()
    shutil.copy(find_repo_root() / "resources" / "config.yaml", tmp_path / "resources" / "config.yaml")
    (tmp_path / "REVISION").write_text("commit=0123456789abcdef\nbranch=main\ndirty=1\n")
    monkeypatch.chdir(tmp_path)          # no .git anywhere above /tmp
    try:
        _bootstrap_resources(tmp_path)
        g = resources.get().git_info
        assert g.commit == "0123456789abcdef+worktree" and g.branch == "main"
        from caml.__version__ import __version__
        assert resources.get().app_version == f"{__version__} [main, 0123456+worktree]"
    finally:
        _bootstrap_resources(find_repo_root())
