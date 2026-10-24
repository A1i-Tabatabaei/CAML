"""The ``caml`` console-script entrypoint.

Replaces AMLB's root-level ``runbenchmark.py`` script with a proper
installed console-script (see ``[project.scripts]`` in pyproject.toml).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from . import leaderboard as leaderboard_mod
from . import prepare as prepare_mod
from . import resources, stats
from . import sweep as sweep_mod
from .benchmark import Benchmark, SetupMode
from .frameworks import installer as installer_mod
from .frameworks.registry import (
    FrameworkNotFoundError,
    discover_frameworks,
)
from .paths import find_repo_root
from .results import Scoreboard
from .utils import Namespace
from .utils.config import config_load

log = logging.getLogger(__name__)


def _bootstrap_resources(repo_root: Path, *, seed: int | None = None, exit_on_job_failure: bool = True):
    config = Namespace(
        user_dir=str(repo_root),
        input_dir=str(repo_root / "input"),
        output_dir=str(repo_root / "output"),
        root_dir=str(repo_root),
        script="caml",
        run_mode="local",
        sid=None,
        job_history=None,
        test_server=False,
        command=" ".join(sys.argv),
        job_scheduler=Namespace(exit_on_job_failure=exit_on_job_failure),
    )
    if seed is not None:
        # An int seed is passed unchanged to every job (AMLB semantics);
        # config.yaml's default `auto` draws a fresh random one per process.
        config.seed = seed
    default_config = config_load(str(repo_root / "resources" / "config.yaml"))
    return resources.from_configs(default_config, config)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def main(verbose: bool):
    """CAML: benchmark the major open-source AutoML frameworks, each in its own isolated environment."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _frameworks_root() -> Path:
    return find_repo_root() / "frameworks"


@main.command()
@click.argument("name", required=False)
@click.option("--all", "install_all", is_flag=True, help="Install every framework.")
@click.option("--latest", is_flag=True, help="Bypass the pin, install latest from PyPI for this run only.")
@click.option("--force", is_flag=True, help="Reinstall even if already up to date.")
def install(name: str | None, install_all: bool, latest: bool, force: bool):
    """Install a framework (or --all of them) into its own uv-managed venv."""
    frameworks_root = _frameworks_root()
    if not install_all and not name:
        raise click.UsageError("Provide a framework NAME or pass --all.")

    targets = (
        list(discover_frameworks(frameworks_root).values())
        if install_all
        else [_get_or_die(frameworks_root, name)]
    )
    if not install_all:
        installer_mod.install(targets[0].manifest, latest=latest, force=force)
        return
    # --all keeps going past a failed install, so one broken framework can't
    # leave the rest uninstalled; the failures are listed and the exit code
    # is non-zero.
    failed = []
    for fw in targets:
        try:
            installer_mod.install(fw.manifest, latest=latest, force=force)
        except Exception as e:  # noqa: BLE001 -- reported below, then exit 1
            log.error("Installing %s failed: %s", fw.name, e)
            failed.append((fw.name, e))
    if failed:
        click.echo(f"\n{len(failed)} of {len(targets)} framework(s) failed to install:", err=True)
        for fw_name, e in failed:
            click.echo(f"  {fw_name}: {str(e).splitlines()[0] if str(e) else type(e).__name__}", err=True)
        sys.exit(1)


def _get_or_die(frameworks_root: Path, name: str):
    from .frameworks.registry import get_framework

    try:
        return get_framework(frameworks_root, name)
    except FrameworkNotFoundError as e:
        raise click.ClickException(str(e)) from e


@main.command()
@click.argument("name")
def uninstall(name: str):
    """Remove a framework's venv and install marker."""
    frameworks_root = _frameworks_root()
    fw = _get_or_die(frameworks_root, name)
    installer_mod.uninstall(fw.manifest)


@main.command()
def status():
    """Print live install status for every discovered framework."""
    frameworks_root = _frameworks_root()
    definitions = discover_frameworks(frameworks_root)
    if not definitions:
        click.echo("No frameworks found under frameworks/.")
        return
    rows = []
    for fw in definitions.values():
        state = installer_mod.read_install_state(fw.manifest.dir)
        if state is None:
            rows.append((fw.name, "not-started", fw.manifest.version_check.current_pin, "-", "-", "-"))
        else:
            ok = state.get("pinned_version") == fw.manifest.version_check.current_pin
            rows.append((
                fw.name,
                "verified" if ok else "stale",
                fw.manifest.version_check.current_pin,
                state.get("installed_version", "?"),
                state.get("python", "?"),
                # compute mode recorded at install time (older markers predate
                # it -> "?"); "n/a" means the framework has no GPU wheel path.
                state.get("compute", "?"),
            ))
    width = max(len(r[0]) for r in rows) + 2
    click.echo(f"{'FRAMEWORK':<{width}}{'STATUS':<12}{'PIN':<12}{'INSTALLED':<14}{'PYTHON':<8}COMPUTE")
    for name, st, pin, installed, py, compute in rows:
        click.echo(f"{name:<{width}}{st:<12}{pin:<12}{installed:<14}{py:<8}{compute}")


def _report_compute() -> None:
    """Report GPU presence + the compute mode CAML would install/run under.

    Purely informational (a CPU box is a valid, supported target) -- it never
    flips doctor's exit code. It reflects the same install-time detection the
    installer uses (nvidia-smi + CAML_COMPUTE), so it's the quickest way to
    confirm a GPU box will actually get CUDA wheels before installing anything.
    """
    override = os.environ.get("CAML_COMPUTE")
    detected = installer_mod.gpu_present()
    if shutil.which("nvidia-smi") is None:
        gpu_line = "no NVIDIA driver (nvidia-smi not found)"
    else:
        try:
            q = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=30,
            )
            gpu_line = q.stdout.strip().replace("\n", "; ") or "nvidia-smi present, no GPU listed"
        except (OSError, subprocess.SubprocessError):
            gpu_line = "nvidia-smi present but query failed"
    mode = "GPU (CUDA wheels)" if detected else "CPU (CPU-only wheels)"
    suffix = f" [CAML_COMPUTE={override}]" if override else ""
    click.echo(f"GPU: {gpu_line}")
    click.echo(f"compute mode: {mode}{suffix}")


@main.command()
def doctor():
    """Sanity-check the environment: uv, apt packages, disk, swap, GPU, stray JVMs."""
    checks_ok = True

    uv_path = shutil.which("uv")
    click.echo(f"uv: {'OK (' + uv_path + ')' if uv_path else 'MISSING'}")
    checks_ok &= bool(uv_path)

    frameworks_root = _frameworks_root()
    definitions = discover_frameworks(frameworks_root)
    apt_needed = sorted({
        pkg
        for fw in definitions.values()
        for pkg in fw.manifest.install.system_packages.apt
    })
    for pkg in apt_needed:
        result = subprocess.run(["dpkg", "-s", pkg], capture_output=True)
        ok = result.returncode == 0
        click.echo(f"apt package {pkg}: {'OK' if ok else 'MISSING'}")
        checks_ok &= ok

    # The filesystem holding the repo (framework venvs, output/), which is
    # not "/" when the workspace lives on another drive (scripts/sync_local.sh).
    disk = shutil.disk_usage(frameworks_root)
    free_gb = disk.free / (1024**3)
    click.echo(
        f"disk free ({frameworks_root.parent}): {free_gb:.1f} GB "
        f"{'OK' if free_gb >= 50 else 'LOW (<50GB recommended)'}"
    )

    _report_compute()

    stray = subprocess.run(["pgrep", "-f", "h2o.jar"], capture_output=True, text=True)
    stray_pids = stray.stdout.split()
    if stray_pids:
        click.echo(f"stray H2O JVM processes: {' '.join(stray_pids)} (consider killing)")
    else:
        click.echo("stray H2O JVM processes: none")

    if not checks_ok:
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--benchmark", "benchmark_name", default="test", show_default=True)
@click.option("--constraint", "constraint_name", default="test", show_default=True)
@click.option("--task", "tasks", type=str, multiple=True, help="Task name(s) to run (default: every task in the benchmark suite).")
@click.option("--fold", "folds", type=int, multiple=True, help="Fold number(s) to run (default: every fold in each task's definition).")
@click.option("--mode", type=click.Choice(["run", "test"]), default="run")
@click.option("--seed", type=int, default=None,
              help="Fixed random seed passed to every job. Default: config.yaml's `auto` (a fresh random seed per invocation, recorded in results.csv).")
@click.option("--keep-going", is_flag=True,
              help="On a job failure, record it as an error row in results.csv (message in `info`) and continue with the remaining jobs, instead of aborting the whole run.")
def run(name: str, benchmark_name: str, constraint_name: str, tasks: tuple[str, ...], folds: tuple[int, ...], mode: str,
        seed: int | None, keep_going: bool):
    """Run a framework against a benchmark suite under a runtime constraint."""
    repo_root = find_repo_root()
    _bootstrap_resources(repo_root, seed=seed, exit_on_job_failure=not keep_going)

    bench = Benchmark(name, benchmark_name, constraint_name)
    bench.setup(SetupMode.auto)
    result = bench.run(tasks=list(tasks) or None, folds=list(folds) or None)
    click.echo(result.to_string(index=False) if hasattr(result, "to_string") else result)


def _fmt(value, spec="{:.4f}") -> str:
    return "n/a" if value is None else spec.format(value)


def _print_compare_result(result: dict, alpha: float, mixed_task_types: bool) -> None:
    excluded = result["excluded_tasks"]

    if result["mode"] == "pairwise":
        a, b = result["framework_a"], result["framework_b"]
        click.echo(f"Comparing: {a} vs {b}")
        click.echo(f"Shared tasks: {result['n_tasks']} (excluded: {len(excluded)})")
        if result["status"] != "no_data":
            click.echo(
                f"Wins: {a}={result['wins_a']}  {b}={result['wins_b']}  "
                f"ties={result['ties']}  mean diff ({a}-{b})={_fmt(result['mean_diff'])}"
            )
        if result["status"] != "ok":
            click.echo(f"No significance test computed: {result['reason']}")
        else:
            w = result["wilcoxon"]
            if w:
                verdict = "significant" if w["significant"] else "not significant"
                click.echo(
                    f"Wilcoxon signed-rank: statistic={_fmt(w['statistic'], '{:.4g}')} "
                    f"p={_fmt(w['p_value'])} -> {verdict} at alpha={alpha}"
                )
            t = result["ttest_rel"]
            if t:
                verdict = "significant" if t["significant"] else "not significant"
                click.echo(
                    f"Paired t-test:         statistic={_fmt(t['statistic'], '{:.4g}')} "
                    f"p={_fmt(t['p_value'])} -> {verdict} at alpha={alpha}"
                )
                if mixed_task_types:
                    click.echo(
                        "  (caveat: compared tasks mix classification and regression "
                        "metrics -- the t-test's raw-magnitude scale isn't commensurable "
                        "across them; prefer the Wilcoxon result)"
                    )
    else:
        click.echo(f"Comparing: {', '.join(result['frameworks'])}")
        click.echo(f"Shared tasks: {result['n_tasks']} (excluded: {len(excluded)})")
        if result["mean_rank"]:
            click.echo("\nMean rank (1=best):")
            for fw, rank in sorted(result["mean_rank"].items(), key=lambda kv: kv[1]):
                click.echo(f"  {fw:<24}{rank:.2f}")
        if result["status"] != "ok":
            click.echo(f"\nNo omnibus significance test computed: {result['reason']}")
        else:
            f = result["friedman"]
            if f:
                verdict = "significant" if f["significant"] else "not significant"
                click.echo(
                    f"\nFriedman test: statistic={_fmt(f['statistic'], '{:.4g}')} "
                    f"p={_fmt(f['p_value'])} -> {verdict} at alpha={alpha}"
                )
        if result["posthoc"]:
            click.echo("\nPost-hoc pairwise (Holm-Bonferroni corrected):")
            click.echo(f"{'FRAMEWORK A':<24}{'FRAMEWORK B':<24}{'WILCOXON P':<14}{'ADJUSTED P':<14}SIGNIFICANT")
            for e in result["posthoc"]:
                sig = "n/a" if e["significant"] is None else str(e["significant"])
                click.echo(
                    f"{e['framework_a']:<24}{e['framework_b']:<24}"
                    f"{_fmt(e['wilcoxon_p']):<14}{_fmt(e['adjusted_p']):<14}{sig}"
                )

    if excluded:
        click.echo("\nExcluded tasks (missing for at least one framework):")
        for task, missing in sorted(excluded.items()):
            click.echo(f"  {task}: missing {', '.join(missing)}")


def _load_results(benchmark_name: str | None, constraint_name: str | None):
    """output/results.csv as a DataFrame, filtered by --benchmark/--constraint."""
    repo_root = find_repo_root()
    _bootstrap_resources(repo_root)

    board = Scoreboard.all(resources.config().output_dir)
    df = board.as_data_frame()
    if df.empty:
        raise click.ClickException("output/results.csv has no rows yet -- run `caml run` first.")

    if constraint_name:
        df = df[df["constraint"] == constraint_name]
    if benchmark_name:
        # benchmark_definition() requires a real TaskConstraint to merge task
        # defaults against, but only task *names*/`enabled` are needed here
        # (neither is affected by which constraint's runtime values are
        # used) -- reuse --constraint if given, else the same "test" default
        # `caml run` itself uses, purely to satisfy that structural requirement.
        constraint_def = resources.get().constraint_definition(constraint_name or "test")
        tasks, _, _ = resources.get().benchmark_definition(benchmark_name, constraint_def)
        task_names = {t.name for t in tasks if Benchmark._is_task_enabled(t)}
        df = df[df["task"].isin(task_names)]
    return df


@main.command()
@click.argument("frameworks", nargs=-1, required=True)
@click.option("--benchmark", "benchmark_name", default=None,
              help="Restrict to this benchmark suite's tasks (resources/benchmarks/<name>.yaml). Default: every task in output/results.csv.")
@click.option("--constraint", "constraint_name", default=None,
              help="Restrict to this runtime constraint. Default: any.")
@click.option("--alpha", type=float, default=0.05, show_default=True,
              help="Significance threshold for the pass/fail verdict shown in output (does not change the computed p-values).")
def compare(frameworks: tuple[str, ...], benchmark_name: str | None, constraint_name: str | None, alpha: float):
    """Statistically compare 2+ frameworks' results in output/results.csv,
    paired per task (mean result across each task's folds). 2 frameworks
    runs a Wilcoxon signed-rank + paired t-test; 3+ runs a Friedman omnibus
    test with a Holm-Bonferroni-corrected pairwise post-hoc.
    """
    if len(frameworks) < 2:
        raise click.UsageError("Provide at least 2 framework names to compare.")

    df = _load_results(benchmark_name, constraint_name)

    missing = set(frameworks) - set(df["framework"].unique())
    if missing:
        available = ", ".join(sorted(df["framework"].unique())) or "(none)"
        raise click.ClickException(
            f"No results for: {', '.join(sorted(missing))} "
            f"(after --benchmark/--constraint filters). Available: {available}"
        )

    result = stats.compare(df, list(frameworks), alpha=alpha)
    mixed_task_types = df[df["framework"].isin(frameworks)]["type"].nunique() > 1
    _print_compare_result(result, alpha, mixed_task_types)


@main.command()
@click.option("--benchmark", "benchmark_name", default=None,
              help="Restrict to this benchmark's tasks: a name in resources/benchmarks/ or a YAML path "
                   "(e.g. the one `caml prepare-data` wrote). Default: every task in output/results.csv.")
@click.option("--constraint", "constraint_name", default=None, help="Restrict to this runtime constraint. Default: any.")
@click.option("--task", "tasks", multiple=True, help="Restrict to these task name(s).")
@click.option("--framework", "frameworks", multiple=True, help="Restrict to these framework(s).")
@click.option("--markdown", is_flag=True, help="Print Markdown tables (for reports and READMEs).")
def leaderboard(benchmark_name: str | None, constraint_name: str | None, tasks: tuple[str, ...],
                frameworks: tuple[str, ...], markdown: bool):
    """Rank frameworks per task by their mean primary metric across folds.

    Built for "which framework is best on my dataset": works with a single
    task, unlike `caml compare` (which tests significance across 2+ tasks).
    Repeated runs of the same job count once (the latest wins).
    """
    df = _load_results(benchmark_name, constraint_name)
    if tasks:
        df = df[df["task"].str.lower().isin({t.lower() for t in tasks})]
    if frameworks:
        df = df[df["framework"].str.lower().isin({f.lower() for f in frameworks})]
    if df.empty:
        raise click.ClickException("No results match those filters.")
    boards = leaderboard_mod.leaderboard(df)
    click.echo("\n\n".join(leaderboard_mod.format_board(b, markdown=markdown) for b in boards))


@main.command("prepare-data")
@click.argument("data_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--target", required=True, help="Name of the column to predict.")
@click.option("--name", default=None, help="Task name used in results (default: the file name).")
@click.option("--type", "task_type", type=click.Choice(["auto", *prepare_mod.TASK_TYPES]), default="auto",
              show_default=True, help="Task type. `auto` infers it from the target and prints why.")
@click.option("--folds", type=click.IntRange(1, 20), default=5, show_default=True,
              help="Cross-validation folds (stratified for classification). 1 = a single train/test holdout.")
@click.option("--test-size", type=click.FloatRange(0.05, 0.5), default=0.2, show_default=True,
              help="Held-out share of rows, used only with --folds 1.")
@click.option("--seed", type=int, default=42, show_default=True, help="Seed for the shuffle/split.")
@click.option("--drop", "drop_columns", multiple=True,
              help="Column to remove before splitting (IDs, leaky or post-outcome columns). Repeatable.")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None,
              help="Where to write the dataset folder. Default: <repo>/input/datasets (gitignored).")
@click.option("--force", is_flag=True, help="Overwrite an existing dataset folder of the same name.")
def prepare_data(data_file: str, target: str, name: str | None, task_type: str, folds: int, test_size: float,
                 seed: int, drop_columns: tuple[str, ...], out_dir: str | None, force: bool):
    """Turn one CSV/TSV/Parquet file into fold files + a benchmark YAML.

    The YAML works with every command that takes --benchmark (run, sweep,
    leaderboard, compare). See skills/caml-benchmark/SKILL.md for the whole
    "benchmark every framework on my data" workflow.
    """
    from .__version__ import __version__

    out = Path(out_dir) if out_dir else find_repo_root() / "input" / "datasets"
    try:
        res = prepare_mod.prepare_dataset(
            data_file, target, out, name=name, task_type=task_type, folds=folds, test_size=test_size,
            seed=seed, drop=drop_columns, force=force, caml_version=__version__,
        )
    except prepare_mod.PrepareError as e:
        raise click.ClickException(str(e))

    split = "1 train/test holdout" if res.folds == 1 else f"{res.folds} folds"
    click.echo(f"Task      {res.name}")
    click.echo(f"Type      {res.task_type}  ({res.type_reason})")
    click.echo(f"Target    {res.target}")
    click.echo(f"Data      {res.rows} rows, {res.feature_columns} feature columns, {split}")
    if res.class_counts:
        shown = ", ".join(f"{k}: {v}" for k, v in list(res.class_counts.items())[:8])
        more = f" (+{len(res.class_counts) - 8} more)" if len(res.class_counts) > 8 else ""
        click.echo(f"Classes   {shown}{more}")
    for w in res.warnings:
        click.echo(f"WARNING   {w}")
    click.echo(f"Wrote     {res.dataset_dir}/")
    click.echo("")
    click.echo("Next (from the repo root):")
    click.echo(f"  caml sweep FLAML AutoGluon --benchmark {res.benchmark_file} --constraint test")
    click.echo(f"  caml leaderboard --benchmark {res.benchmark_file}")


@main.command()
@click.argument("frameworks", nargs=-1, required=True)
@click.option("--benchmark", "benchmark_name", required=True,
              help="Benchmark suite: resources/benchmarks/<name>.yaml, or an OpenML suite/task (openml/s/<id>, openml/t/<id>).")
@click.option("--constraint", "constraint_name", required=True,
              help="Runtime constraint from resources/constraints.yaml (sets folds, time budget, cores).")
@click.option("--task", "tasks", type=str, multiple=True, help="Restrict to these task name(s). Default: every enabled task.")
@click.option("--fold", "folds", type=int, multiple=True, help="Restrict to these fold number(s). Default: every fold.")
@click.option("--seed", type=int, default=42, show_default=True, help="Fixed seed passed to every job, for reproducibility.")
@click.option("--shard", default="1/1", show_default=True,
              help="Run only shard K of N (e.g. 2/4): split one sweep across N boxes with no coordination.")
@click.option("--name", "sweep_name", default=None,
              help="Sweep name (its ledger + logs live in output/sweeps/<name>/). Default: <benchmark>-<constraint>.")
@click.option("--retry-failed", is_flag=True, help="Also re-run jobs whose latest ledger record is a failure.")
@click.option("--max-jobs", type=int, default=None, help="Run at most this many pending jobs, then stop.")
@click.option("--job-timeout", type=int, default=None,
              help=f"Hard wall-clock limit per job, seconds. Default: 2 x the task's time budget + {sweep_mod.HARD_TIMEOUT_MARGIN_SECS // 60} min.")
@click.option("--dry-run", is_flag=True, help="Print the job matrix and each job's ledger status; run nothing.")
def sweep(frameworks: tuple[str, ...], benchmark_name: str, constraint_name: str, tasks: tuple[str, ...],
          folds: tuple[int, ...], seed: int, shard: str, sweep_name: str | None, retry_failed: bool,
          max_jobs: int | None, job_timeout: int | None, dry_run: bool):
    """Run FRAMEWORKS x tasks x folds as isolated, resumable, failure-classified
    jobs (one `caml run --keep-going` subprocess per job). Re-run the same
    command to resume. See docs/operations/sweeps.md.
    """
    try:
        shard_k, shard_n = sweep_mod.parse_shard(shard)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--shard")

    repo_root = find_repo_root()
    _bootstrap_resources(repo_root)
    res = resources.get()

    canonical = []
    for name in frameworks:
        try:
            fdef, resolved = res.framework_definition(name)
        except FrameworkNotFoundError as e:
            raise click.ClickException(str(e))
        if not dry_run and not installer_mod.is_installed(fdef.manifest.dir, fdef.manifest):
            raise click.ClickException(f"{resolved} is not installed -- run `caml install {resolved}` first.")
        canonical.append(resolved)

    constraint_def = res.constraint_definition(constraint_name)
    task_defs, _, _ = res.benchmark_definition(benchmark_name, constraint_def)
    task_defs = [t for t in task_defs if Benchmark._is_task_enabled(t)]
    if tasks:
        # Case-insensitive, matching `caml run --task`.
        wanted = {t.lower() for t in tasks}
        unknown = sorted(t for t in tasks if t.lower() not in {d.name.lower() for d in task_defs})
        if unknown:
            raise click.ClickException(f"Unknown task(s) for {benchmark_name}: {', '.join(unknown)}")
        task_defs = [t for t in task_defs if t.name.lower() in wanted]
    specs = [sweep_mod.TaskSpec(t.name, int(t.folds), int(t.max_runtime_seconds)) for t in task_defs]

    jobs = sweep_mod.build_matrix(canonical, specs, folds=list(folds) or None)
    jobs = sweep_mod.select_shard(jobs, shard_k, shard_n)
    sweep_dir = Path(resources.config().output_dir) / "sweeps" / (sweep_name or sweep_mod.default_sweep_name(benchmark_name, constraint_name))

    if dry_run:
        latest = sweep_mod.Ledger(sweep_dir / "ledger.jsonl").latest()
        for job in jobs:
            rec = latest.get(job.key)
            click.echo(f"{job.framework:<18}{job.task:<28}fold {job.fold:<4}{rec['status'] if rec else 'pending'}")
        click.echo("")
        click.echo(sweep_mod.format_summary(sweep_mod.summarize(jobs, latest)))
        return

    caml_exe = str(Path(sys.executable).with_name("caml"))
    if not os.access(caml_exe, os.X_OK):
        caml_exe = shutil.which("caml") or caml_exe
    try:
        summary = sweep_mod.run_sweep(
            jobs,
            sweep_dir=sweep_dir,
            results_csv=Path(resources.config().output_dir) / "results.csv",
            benchmark=benchmark_name,
            constraint=constraint_name,
            seed=seed,
            caml_exe=caml_exe,
            app_version=res.app_version,
            job_timeout=job_timeout,
            max_jobs=max_jobs,
            retry_failed=retry_failed,
            echo=click.echo,
        )
    except sweep_mod.SweepLockedError as e:
        raise click.ClickException(str(e))
    click.echo("")
    click.echo(sweep_mod.format_summary(summary))
    click.echo(f"\nLedger: {sweep_dir / 'ledger.jsonl'}")
    if summary["interrupted"]:
        sys.exit(130)


@main.command("check-versions")
def check_versions():
    """Diff each framework's current_pin against the latest release on PyPI."""
    import requests

    frameworks_root = _frameworks_root()
    for fw in discover_frameworks(frameworks_root).values():
        pkg = fw.manifest.version_check.pypi_package
        pin = fw.manifest.version_check.current_pin
        try:
            resp = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=10)
            resp.raise_for_status()
            latest = resp.json()["info"]["version"]
        except Exception as e:
            click.echo(f"{fw.name}: could not check PyPI ({e})")
            continue
        marker = "UP TO DATE" if latest == pin else f"NEW RELEASE AVAILABLE: {latest}"
        click.echo(f"{fw.name}: pinned={pin} latest={latest} [{marker}]")


if __name__ == "__main__":
    main()
