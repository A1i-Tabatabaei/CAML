"""Run a large (frameworks x tasks x folds) benchmark matrix robustly.

``caml run`` is the right tool for one framework on one benchmark, but a
paper-scale sweep (10 frameworks x dozens of tasks x 10 folds, spread over
several boxes, running for days) needs things ``caml run`` doesn't give:

- **failure isolation**: every job runs as its own ``caml run ... --task T
  --fold F --keep-going`` subprocess, so a framework that crashes, hangs or
  gets OOM-killed on one task can't take the rest of the sweep down with it;
- **resume**: an append-only JSONL ledger records each finished job, so a
  re-run skips everything already done (and an interrupted job, which never
  got a ledger record, simply runs again);
- **failure classification**: each job ends as one of ``STATUSES`` below, so
  failures can be reported honestly instead of silently vanishing from
  ``results.csv``;
- **sharding**: ``--shard K/N`` deterministically splits one matrix across N
  boxes with no coordination between them;
- **reproducibility**: a fixed seed is passed to every job, and each ledger
  record carries the CAML revision, framework version and host specs.

Pure logic (matrix building, sharding, resume, classification) lives in
plain functions so it is unit-testable without running any framework; only
``run_job()`` touches real subprocesses.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import socket
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

#: Every job ends in exactly one of these.
#: - ok:        a results.csv row with a real score was written.
#: - error:     a results.csv row was written, but with no score -- the
#:              framework raised and ``--keep-going`` recorded the error
#:              (its message is in the row's ``info`` column).
#: - timeout:   the job exceeded the sweep's hard wall-clock limit and was
#:              killed (a hang, or a framework ignoring its time budget).
#: - killed:    the job process died from a signal (SIGKILL usually means
#:              the kernel OOM killer -- check ``dmesg``).
#: - crash:     the job exited non-zero without writing any row.
#: - no_result: the job exited 0 but wrote no row (should not happen).
STATUSES = ("ok", "error", "timeout", "killed", "crash", "no_result")
FAILED_STATUSES = frozenset(STATUSES) - {"ok"}

#: Extra wall-clock allowance on top of 2 x the task's time budget before the
#: sweep hard-kills a job. A job's own internal timeout is already
#: ``min(2 x budget, budget + 1h) + 5min`` (config.yaml's overhead settings
#: plus Job's safety margin), so this only fires on a genuine hang -- it also
#: covers dataset download and framework start-up, which the internal
#: timeout doesn't.
HARD_TIMEOUT_MARGIN_SECS = 20 * 60

#: Seconds to wait after SIGTERM before escalating to SIGKILL.
_TERM_GRACE_SECS = 30


@dataclass(frozen=True)
class TaskSpec:
    name: str
    folds: int
    max_runtime_seconds: int


@dataclass(frozen=True)
class SweepJob:
    framework: str
    task: str
    fold: int
    max_runtime_seconds: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.framework, self.task, self.fold)

    @property
    def log_name(self) -> str:
        return f"{self.framework}.{_sanitize(self.task)}.{self.fold}.log"


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")


def default_sweep_name(benchmark: str, constraint: str) -> str:
    # A benchmark given as a YAML path (e.g. one `caml prepare-data` wrote)
    # is named by its file stem, like results.csv does, not the whole path.
    if benchmark.lower().endswith((".yaml", ".yml")):
        benchmark = Path(benchmark).stem
    return _sanitize(f"{benchmark}-{constraint}")


def build_matrix(
    frameworks: Iterable[str],
    tasks: Iterable[TaskSpec],
    folds: Iterable[int] | None = None,
) -> list[SweepJob]:
    """Fold-major order (fold 0 of every task for every framework, then fold
    1, ...), so a sweep stopped early still holds *complete, paired*
    comparisons -- every framework on the same (task, fold) cells -- instead
    of all ten folds of the first framework and nothing for the rest.
    """
    frameworks = list(frameworks)
    tasks = list(tasks)
    wanted = None if folds is None else set(folds)
    max_folds = max((t.folds for t in tasks), default=0)
    jobs = []
    for fold in range(max_folds):
        if wanted is not None and fold not in wanted:
            continue
        for task in tasks:
            if fold >= task.folds:
                continue
            for fw in frameworks:
                jobs.append(SweepJob(fw, task.name, fold, task.max_runtime_seconds))
    return jobs


def parse_shard(spec: str) -> tuple[int, int]:
    """``"K/N"`` -> ``(K, N)`` with 1 <= K <= N."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", spec or "")
    if not m:
        raise ValueError(f"shard must look like K/N (e.g. 2/4), got {spec!r}")
    k, n = int(m.group(1)), int(m.group(2))
    if n < 1 or not 1 <= k <= n:
        raise ValueError(f"shard K/N needs 1 <= K <= N, got {spec!r}")
    return k, n


def select_shard(jobs: list[SweepJob], k: int, n: int) -> list[SweepJob]:
    """Round-robin over the *full* matrix order, so shard membership never
    depends on what has already run -- every box computes the same split
    independently.
    """
    return [job for i, job in enumerate(jobs) if i % n == k - 1]


def hard_timeout_secs(job: SweepJob, override: int | None = None) -> int:
    if override is not None:
        return override
    return 2 * job.max_runtime_seconds + HARD_TIMEOUT_MARGIN_SECS


class Ledger:
    """Append-only JSONL record of finished jobs; the latest record per job
    key wins (so ``--retry-failed`` re-runs simply append a newer record).
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    # A torn final line from a hard kill mid-write: ignore it,
                    # that job just counts as not-yet-done and re-runs.
                    continue
        return out

    def latest(self) -> dict[tuple[str, str, int], dict]:
        latest = {}
        for rec in self.records():
            latest[(rec["framework"], rec["task"], int(rec["fold"]))] = rec
        return latest

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())


def pending_jobs(
    jobs: list[SweepJob], latest: dict[tuple[str, str, int], dict], retry_failed: bool = False
) -> list[SweepJob]:
    """Jobs with no ledger record yet, plus (with ``retry_failed``) jobs whose
    latest record is a failure. ``ok`` jobs are never re-run.
    """
    out = []
    for job in jobs:
        rec = latest.get(job.key)
        if rec is None:
            out.append(job)
        elif retry_failed and rec.get("status") in FAILED_STATUSES:
            out.append(job)
    return out


def classify(returncode: int | None, timed_out: bool, new_rows: pd.DataFrame) -> tuple[str, str]:
    """Map a finished job's exit state + the results.csv rows it wrote to one
    of ``STATUSES`` and a short human-readable detail.
    """
    scored = new_rows[new_rows["result"].notna()] if not new_rows.empty else new_rows
    if not scored.empty:
        return "ok", ""
    if timed_out:
        return "timeout", "killed by the sweep's hard wall-clock limit"
    if not new_rows.empty:
        infos = new_rows["info"].dropna().astype(str) if "info" in new_rows else pd.Series(dtype=str)
        return "error", (infos.iloc[-1] if not infos.empty else "row written without a score")
    if returncode is not None and returncode < 0:
        return "killed", f"terminated by signal {-returncode} ({_signal_name(-returncode)})"
    if returncode is not None and returncode > 128 and returncode - 128 in _KNOWN_SIGNALS:
        # A shell between us and the process reports a signal death as 128+N.
        return "killed", f"exit code {returncode} = signal {returncode - 128} ({_signal_name(returncode - 128)})"
    if returncode:
        return "crash", f"exit code {returncode}"
    return "no_result", "exited 0 but wrote no results.csv row"


_KNOWN_SIGNALS = {int(s) for s in signal.Signals}


def _signal_name(num: int) -> str:
    try:
        return signal.Signals(num).name
    except ValueError:
        return "unknown"


def read_results(results_csv: Path) -> pd.DataFrame:
    if not Path(results_csv).exists():
        return pd.DataFrame(columns=["framework", "task", "constraint", "fold", "result", "info"])
    return pd.read_csv(results_csv)


def rows_for(df: pd.DataFrame, job: SweepJob, constraint: str) -> pd.DataFrame:
    if df.empty:
        return df
    mask = (
        (df["framework"] == job.framework)
        & (df["task"] == job.task)
        & (df["constraint"] == constraint)
        & (pd.to_numeric(df["fold"], errors="coerce") == job.fold)
    )
    return df[mask]


def tail_line(path: Path, max_bytes: int = 4096) -> str:
    """Last non-empty line of a log -- usually the error that ended a crash."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            lines = [ln.strip() for ln in f.read().decode(errors="replace").splitlines()]
    except OSError:
        return ""
    lines = [ln for ln in lines if ln]
    return lines[-1][:300] if lines else ""


def host_info() -> dict:
    mem_gb = None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_gb = round(int(line.split()[1]) / 1024 / 1024, 1)
                    break
    except OSError:
        pass
    return {"host": socket.gethostname(), "cpus": os.cpu_count(), "mem_gb": mem_gb}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SweepLockedError(RuntimeError):
    pass


class SweepLock:
    """Non-blocking exclusive lock on the sweep directory: refuses to start a
    second driver on the same sweep (two concurrent drivers would double-run
    jobs and, on a small box, run out of memory -- a real failure this
    project already hit on 2026-09-15).
    """

    def __init__(self, sweep_dir: Path):
        self.path = Path(sweep_dir) / ".lock"
        self._fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.path, "w")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._fd.close()
            raise SweepLockedError(
                f"another `caml sweep` is already running on {self.path.parent} "
                "(check `ps aux | grep '[c]aml sweep'`)"
            )
        self._fd.write(str(os.getpid()))
        self._fd.flush()
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()


class _Interrupted(Exception):
    pass


def run_job(cmd: list[str], log_path: Path, timeout_secs: int) -> tuple[int | None, bool, float]:
    """Run one job in its own process group, output to ``log_path``.

    Returns ``(returncode, timed_out, wall_seconds)``. The whole process group
    is killed afterwards in every case, so stray children (framework worker
    pools, an H2O JVM) can't survive into the next job and eat its memory.
    Raises ``_Interrupted`` (after killing the job) if the driver itself gets
    SIGINT/SIGTERM, so that job is left unrecorded and re-runs on resume.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    timed_out = False
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

        def on_signal(signum, _frame):
            raise _Interrupted(signum)

        old_int = signal.signal(signal.SIGINT, on_signal)
        old_term = signal.signal(signal.SIGTERM, on_signal)
        try:
            try:
                proc.wait(timeout=timeout_secs)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
        except _Interrupted:
            _kill_group(proc)
            raise
        finally:
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
            _reap_group(proc.pid)
    return proc.returncode, timed_out, time.monotonic() - start


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=_TERM_GRACE_SECS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def _reap_group(pgid: int) -> None:
    """SIGKILL anything still left in the job's process group."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def job_command(caml_exe: str, job: SweepJob, benchmark: str, constraint: str, seed: int) -> list[str]:
    return [
        caml_exe, "run", job.framework,
        "--benchmark", benchmark,
        "--constraint", constraint,
        "--task", job.task,
        "--fold", str(job.fold),
        "--seed", str(seed),
        "--keep-going",
    ]


def run_sweep(
    jobs: list[SweepJob],
    *,
    sweep_dir: Path,
    results_csv: Path,
    benchmark: str,
    constraint: str,
    seed: int,
    caml_exe: str,
    app_version: str,
    job_timeout: int | None = None,
    max_jobs: int | None = None,
    retry_failed: bool = False,
    echo: Callable[[str], None] = print,
    runner: Callable[[list[str], Path, int], tuple[int | None, bool, float]] = run_job,
) -> dict:
    """Run every pending job in ``jobs`` sequentially; return a summary.

    ``runner`` is injectable so the bookkeeping can be tested without
    launching real frameworks.
    """
    sweep_dir = Path(sweep_dir)
    ledger = Ledger(sweep_dir / "ledger.jsonl")
    host = host_info()
    interrupted = False
    with SweepLock(sweep_dir):
        todo = pending_jobs(jobs, ledger.latest(), retry_failed=retry_failed)
        if max_jobs is not None:
            todo = todo[:max_jobs]
        echo(f"{len(jobs)} jobs in this shard, {len(todo)} to run now.")
        for i, job in enumerate(todo, 1):
            timeout = hard_timeout_secs(job, job_timeout)
            log_path = sweep_dir / "logs" / job.log_name
            before = len(rows_for(read_results(results_csv), job, constraint))
            started = utc_now()
            echo(f"[{i}/{len(todo)}] {job.framework} / {job.task} / fold {job.fold} "
                 f"(budget {job.max_runtime_seconds}s, hard limit {timeout}s) ...")
            cmd = job_command(caml_exe, job, benchmark, constraint, seed)
            try:
                returncode, timed_out, wall = runner(cmd, log_path, timeout)
            except _Interrupted:
                echo("Interrupted: the current job was killed and left unrecorded; "
                     "re-run the same command to resume.")
                interrupted = True
                break
            new_rows = rows_for(read_results(results_csv), job, constraint).iloc[before:]
            status, detail = classify(returncode, timed_out, new_rows)
            if status in ("crash", "no_result"):
                last = tail_line(log_path)
                if last:
                    detail = f"{detail}; last log line: {last}"
            row = new_rows.iloc[-1] if not new_rows.empty else None

            def field(name):
                if row is None or name not in row or pd.isna(row[name]):
                    return None
                value = row[name]
                return value.item() if hasattr(value, "item") else value

            ledger.append({
                "framework": job.framework,
                "task": job.task,
                "fold": job.fold,
                "benchmark": benchmark,
                "constraint": constraint,
                "seed": seed,
                "status": status,
                "detail": detail,
                "returncode": returncode,
                "result": field("result"),
                "metric": field("metric"),
                "framework_version": field("version"),
                "app_version": field("app_version") or app_version,
                "max_runtime_seconds": job.max_runtime_seconds,
                "hard_timeout_seconds": timeout,
                "wall_seconds": round(wall, 1),
                "started_utc": started,
                "ended_utc": utc_now(),
                "log": str(log_path.relative_to(sweep_dir)),
                **host,
            })
            score = f" {field('metric')}={field('result'):.4f}" if status == "ok" and field("result") is not None else ""
            echo(f"    -> {status}{score}{(': ' + detail) if detail else ''} ({wall:.0f}s)")
    summary = summarize(jobs, ledger.latest())
    summary["interrupted"] = interrupted
    return summary


def summarize(jobs: list[SweepJob], latest: dict[tuple[str, str, int], dict]) -> dict:
    """Per-framework status counts over ``jobs`` (``pending`` = no record yet)."""
    per_fw: dict[str, Counter] = {}
    for job in jobs:
        rec = latest.get(job.key)
        status = rec["status"] if rec else "pending"
        per_fw.setdefault(job.framework, Counter())[status] += 1
    return {"per_framework": per_fw, "total": len(jobs)}


def format_summary(summary: dict) -> str:
    columns = ["pending", *STATUSES]
    header = f"{'FRAMEWORK':<20}" + "".join(f"{c.upper():>10}" for c in columns)
    lines = [header]
    for fw, counts in sorted(summary["per_framework"].items()):
        lines.append(f"{fw:<20}" + "".join(f"{counts.get(c, 0):>10}" for c in columns))
    return "\n".join(lines)
