"""scripts/camlctl: the one server command every operator OS uses over SSH.

camlctl normally runs as root and drops to the `caml` user with sudo. Here it
runs as the current user (CAMLCTL_ALLOW_NONROOT=1 with CAMLCTL_USER set to
ourselves), against a throwaway home and repo, with a stand-in `uv` that
records its arguments and fakes `caml` output. CI's server-e2e job runs the
real thing as root on Ubuntu 24.04, over SSH (tests/e2e/agent_flow.sh).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAMLCTL = ROOT / "scripts" / "camlctl"

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("setsid") is None,
    reason="camlctl runs on the Ubuntu server: needs Linux, /proc and setsid",
)

FAKE_UV = r"""#!/usr/bin/env bash
printf '%s\n' "$PWD" > "$FAKE_UV_DIR/cwd"
printf '%s\n' "$@" > "$FAKE_UV_DIR/args"
printf '%s\n' "${CAMLCTL_JOB:-}" > "$FAKE_UV_DIR/job"
[[ "$1" == "--version" ]] && { echo "uv 0.0.0-fake"; exit 0; }
[[ "$1" == "run" ]] && shift
case "$1 ${2:-}" in
  "caml install")
    [[ "$3" == "Broken" ]] && { echo "Broken: build failed" >&2; exit 1; }
    echo "installed $3"; exit 0 ;;
  "caml sweep")
    if [[ " $* " == *" --dry-run "* ]]; then
      echo "FLAML             t                           fold 0   ok"
      echo
      echo "FRAMEWORK              PENDING        OK"
      echo "FLAML                        1         1"
      exit 0
    fi
    echo "2 jobs in this shard, 2 to run now."
    echo "[1/2] FLAML / t / fold 0 (budget 60s, hard limit 1320s) ..."
    sleep "${FAKE_SWEEP_SECS:-1}"
    echo "  -> ok auc=0.9 (1s)"
    exit "${FAKE_SWEEP_RC:-0}" ;;
  "caml fail") echo "boom" >&2; exit 7 ;;
  "python "*) shift; exec python3 "$@" ;;
esac
echo "fake caml: $*"
"""


class Ctl:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        self.repo = self.home / "caml-workspace" / "CAML"
        self.data = self.home / "data"
        self.state = tmp / "state"
        self.bundles = tmp / "bundles"
        self.uploads = tmp / "uploads"
        self.fake = tmp / "fake"
        bindir = tmp / "bin"
        for d in (self.repo / "src" / "caml", self.uploads, self.fake, bindir):
            d.mkdir(parents=True)
        (self.repo / "pyproject.toml").write_text("[project]\nname='caml'\n")
        (self.repo / "src" / "caml" / "__version__.py").write_text('__version__ = "9.9.9"\n')
        uv = bindir / "uv"
        uv.write_text(FAKE_UV)
        uv.chmod(0o755)
        me = subprocess.run(["id", "-un"], capture_output=True, text=True, check=True).stdout.strip()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CAMLCTL_", "FAKE_")) and k != "TABPFN_TOKEN"}
        env.update(
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            CAMLCTL_ALLOW_NONROOT="1",
            CAMLCTL_USER=me,
            CAMLCTL_HOME=str(self.home),
            CAMLCTL_REPO=str(self.repo),
            CAMLCTL_DATA=str(self.data),
            CAMLCTL_STATE=str(self.state),
            CAMLCTL_BIN=str(tmp / "installed-camlctl"),
            CAMLCTL_BUNDLES=str(self.bundles),
            FAKE_UV_DIR=str(self.fake),
        )
        self.env = env

    def __call__(self, *args: str, cwd: Path | None = None, extra_env: dict | None = None,
                 timeout: float = 90, stdin=subprocess.DEVNULL) -> subprocess.CompletedProcess:
        env = {**self.env, **(extra_env or {})}
        return subprocess.run(["bash", str(CAMLCTL), *args], cwd=cwd or self.uploads, env=env,
                              capture_output=True, text=True, timeout=timeout, stdin=stdin)

    def uv_args(self) -> list[str]:
        return (self.fake / "args").read_text().splitlines()

    def wait_done(self, job: str, secs: int = 30) -> subprocess.CompletedProcess:
        return self("wait", job, str(secs), timeout=secs + 30)


@pytest.fixture
def ctl(tmp_path: Path):
    c = Ctl(tmp_path)
    yield c
    # Never leave a detached test job behind.
    jobs = c.state / "jobs"
    if jobs.is_dir():
        for pid_file in jobs.glob("*.pid"):
            name = pid_file.stem
            if not (jobs / f"{name}.exit").exists():
                c("stop", name, timeout=120)


def kv(output: str) -> dict[str, str]:
    """The `key: value` lines camlctl prints for agents to parse."""
    out = {}
    for line in output.splitlines():
        m = re.match(r"^([a-z_0-9]+): (.*)$", line)
        if m:
            out.setdefault(m.group(1), m.group(2))
    return out


def test_help_runs_without_root_and_names_the_ssh_shape(tmp_path: Path):
    r = subprocess.run(["bash", str(CAMLCTL), "help"], capture_output=True, text=True,
                       env={"PATH": os.environ["PATH"]})
    assert r.returncode == 0
    assert "ssh caml-vps camlctl <command>" in r.stdout
    for command in ("info", "setup", "caml", "install", "dataset", "script", "start", "jobs",
                    "logs", "wait", "stop", "status", "bundle", "tabpfn-token", "update", "version"):
        assert re.search(rf"^  {re.escape(command)}\b", r.stdout, re.M), command


def test_unknown_command_is_a_usage_error(ctl: Ctl):
    r = ctl("frobnicate")
    assert r.returncode == 2
    assert "unknown command" in r.stderr


def test_version_matches_the_package():
    ctl_version = re.search(r'^CAMLCTL_VERSION="(.*)"$', CAMLCTL.read_text(), re.M).group(1)
    pkg = re.search(r'^__version__ = "(.*)"$', (ROOT / "src/caml/__version__.py").read_text(), re.M).group(1)
    assert ctl_version == pkg


def test_version_and_offline_info(ctl: Ctl):
    r = ctl("version")
    assert r.returncode == 0
    assert "camlctl " in r.stdout and "caml 9.9.9" in r.stdout
    r = ctl("info", "--offline")
    assert r.returncode == 0, r.stderr
    info = kv(r.stdout)
    for key in ("os", "arch", "cpus", "ram_gib", "disk_free_gib", "caml_user", "caml", "jobs_running", "checks"):
        assert key in info, key
    assert info["caml"].startswith("9.9.9")
    assert info["jobs_running"] == "none"
    assert "net_pypi" not in info  # --offline skips the network


def test_caml_runs_in_the_repo_and_keeps_arguments(ctl: Ctl):
    r = ctl("caml", "prepare-data", "/home/caml/data/x.csv", "--target", "two words", "--folds", "5")
    assert r.returncode == 0, r.stderr
    assert ctl.uv_args() == ["run", "caml", "prepare-data", "/home/caml/data/x.csv", "--target", "two words", "--folds", "5"]
    assert (ctl.fake / "cwd").read_text().strip() == str(ctl.repo)


def test_caml_propagates_the_exit_code(ctl: Ctl):
    r = ctl("caml", "fail")
    assert r.returncode == 7
    assert "boom" in r.stderr


def test_caml_suggests_detaching_long_commands(ctl: Ctl):
    assert "camlctl start JOB caml sweep" in ctl("caml", "sweep", "FLAML", "--benchmark", "b").stderr
    assert "tip" not in ctl("caml", "sweep", "FLAML", "--benchmark", "b", "--dry-run").stderr


def test_caml_before_setup_says_what_to_do(ctl: Ctl):
    shutil.rmtree(ctl.repo)
    r = ctl("caml", "status")
    assert r.returncode == 1
    assert "camlctl setup --detach" in r.stderr


def test_install_keeps_going_and_reports(ctl: Ctl):
    r = ctl("install", "FLAML", "Broken", "TPOT")
    assert r.returncode == 1
    assert "installed: FLAML TPOT" in r.stdout
    assert "failed: Broken" in r.stdout
    assert ctl("install").returncode == 2
    assert ctl("install", "--all").returncode == 0
    assert ctl.uv_args() == ["run", "caml", "install", "--all"]


def test_job_runs_detached_and_reports_done(ctl: Ctl):
    r = ctl("start", "sweep", "caml", "sweep", "FLAML", "--benchmark", "input/datasets/t/t.yaml", "--constraint", "quick")
    assert r.returncode == 0, r.stderr
    assert "started job sweep" in r.stdout and "camlctl wait sweep" in r.stdout
    w = ctl.wait_done("sweep")
    assert w.returncode == 0, w.stdout + w.stderr
    assert "job sweep: done" in w.stdout
    jobs = ctl("jobs").stdout
    assert re.search(r"^sweep\s+done\s+0\s", jobs, re.M), jobs
    log = ctl("logs", "sweep").stdout
    assert "[1/2] FLAML / t / fold 0" in log and "== finished" in log
    assert (ctl.fake / "job").read_text().strip() == "sweep"  # the marker `stop` relies on


def test_failed_job_reports_its_exit_code(ctl: Ctl):
    ctl("start", "sweep", "caml", "sweep", "FLAML", extra_env={"FAKE_SWEEP_RC": "3"})
    w = ctl.wait_done("sweep")
    assert w.returncode == 1
    assert "job sweep: failed (exit 3)" in w.stdout


def test_wait_times_out_then_stop_ends_everything(ctl: Ctl):
    ctl("start", "long", "caml", "sweep", "FLAML", extra_env={"FAKE_SWEEP_SECS": "120"})
    w = ctl("wait", "long", "1")
    assert w.returncode == 124
    assert "job long: running" in w.stdout
    again = ctl("start", "long", "caml", "status")
    assert again.returncode == 3 and "already running" in again.stderr
    t0 = time.monotonic()
    s = ctl("stop", "long", timeout=120)
    assert s.returncode == 0, s.stderr
    assert time.monotonic() - t0 < 30, "SIGTERM should end the job; the SIGKILL fallback waits 60s"
    assert "job long: failed" in s.stdout
    time.sleep(0.5)
    left = subprocess.run(["pgrep", "-f", "__job long"], capture_output=True, text=True).stdout
    assert left == ""
    sleeper = subprocess.run(["pgrep", "-f", "^sleep 120$"], capture_output=True, text=True).stdout
    assert sleeper == "", "the job's child process survived camlctl stop"


def test_rerunning_a_job_name_keeps_the_previous_run(ctl: Ctl):
    ctl("start", "sweep", "caml", "sweep", "FLAML")
    ctl.wait_done("sweep")
    time.sleep(1.1)  # distinct start stamps
    ctl("start", "sweep", "caml", "sweep", "FLAML", extra_env={"FAKE_SWEEP_RC": "2"})
    ctl.wait_done("sweep")
    history = list((ctl.state / "jobs" / "history").glob("sweep.*.exit"))
    assert len(history) == 1 and history[0].read_text().strip() == "0"
    assert (ctl.state / "jobs" / "sweep.exit").read_text().strip() == "2"


@pytest.mark.parametrize("name", ["../etc", "has space", "", "-x", "a" * 65])
def test_job_names_are_validated(ctl: Ctl, name: str):
    assert ctl("start", name, "caml", "status").returncode == 2


def test_start_only_runs_camlctl_work_commands(ctl: Ctl):
    r = ctl("start", "x", "bash", "-c", "id")
    assert r.returncode == 2


def test_status_shows_health_jobs_and_sweep_progress(ctl: Ctl):
    ctl("start", "sweep", "caml", "sweep", "FLAML", "--benchmark", "b.yaml", "--constraint", "quick")
    ctl.wait_done("sweep")
    r = ctl("status")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "memory:" in out and "disk:" in out and "oom kills since boot:" in out
    assert "== sweep job sweep (done" in out
    assert "[1/2] FLAML / t / fold 0" in out
    assert re.search(r"^FRAMEWORK\s+PENDING\s+OK", out, re.M)
    assert ctl.uv_args() == ["run", "caml", "sweep", "FLAML", "--benchmark", "b.yaml", "--constraint", "quick", "--dry-run"]


def test_dataset_moves_the_upload_and_describes_it(ctl: Ctl):
    body = b"customer_id,age,churned\n1,34,yes\n2,51,no\n3,29,yes\n"
    (ctl.uploads / "upload.csv").write_bytes(body)
    r = ctl("dataset", "upload.csv", "--name", "churn.csv")
    assert r.returncode == 0, r.stderr
    info = kv(r.stdout)
    dest = ctl.data / "churn.csv"
    assert info["path"] == str(dest)
    assert not (ctl.uploads / "upload.csv").exists()
    assert dest.read_bytes() == body
    assert (dest.stat().st_mode & 0o777) == 0o600
    assert info["sha256"] == hashlib.sha256(body).hexdigest()
    assert info["encoding"] == "utf-8"
    assert info["separator"] == "comma"
    assert info["columns"].startswith("3 ")
    assert info["rows"].startswith("3 ")
    assert info["status"] == "ok"
    assert info["next"].startswith(f"camlctl caml prepare-data {dest} --target")


def test_dataset_semicolon_crlf_bom_and_no_final_newline(ctl: Ctl):
    (ctl.uploads / "eu.csv").write_bytes(b"\xef\xbb\xbfa;b;c;y\r\n1,5;2;3;x\r\n4,5;5;6;z")
    info = kv(ctl("dataset", "eu.csv").stdout)
    assert info["encoding"].startswith("utf-8 (with a BOM")
    assert info["line_endings"].startswith("CRLF")
    assert info["separator"] == "semicolon"
    assert info["columns"].startswith("4 ")
    assert info["rows"].startswith("2 ")
    assert info["header"] == "a;b;c;y"


def test_dataset_flags_windows_1252_and_converts_it(ctl: Ctl):
    body = "name;price;y\r\ncafé;1,5;yes\r\nthé;2,0;no\r\n".encode("cp1252")
    (ctl.uploads / "excel.csv").write_bytes(body)
    first = kv(ctl("dataset", "excel.csv").stdout)
    assert first["encoding"].startswith("NOT UTF-8")
    assert first["status"] == "needs-conversion"
    assert first["fix"].startswith(f"camlctl dataset {ctl.data / 'excel.csv'} --from-encoding WINDOWS-1252")
    r = ctl("dataset", str(ctl.data / "excel.csv"), "--from-encoding", "WINDOWS-1252")
    assert r.returncode == 0, r.stderr
    second = kv(r.stdout)
    assert second["sha256"] == hashlib.sha256(body).hexdigest()  # the upload, before conversion
    assert second["encoding"] == "utf-8" and second["status"] == "ok"
    assert (ctl.data / "excel.csv").read_text(encoding="utf-8").splitlines()[1] == "café;1,5;yes"
    assert (ctl.data / "excel.csv.orig").read_bytes() == body
    assert ctl("dataset", str(ctl.data / "excel.csv"), "--from-encoding", "WINDOWS-1252").returncode == 3


def test_dataset_rejects_excel_workbooks(ctl: Ctl):
    (ctl.uploads / "book.csv").write_bytes(b"PK\x03\x04" + b"\0" * 64)
    r = ctl("dataset", "book.csv")
    assert r.returncode == 2
    assert kv(r.stdout)["status"] == "unsupported"
    assert "CSV UTF-8" in r.stdout


def test_dataset_accepts_parquet(ctl: Ctl):
    (ctl.uploads / "t.parquet").write_bytes(b"PAR1" + b"\0" * 32 + b"PAR1")
    info = kv(ctl("dataset", "t.parquet").stdout)
    assert info["format"] == "parquet" and info["status"] == "ok"


def test_dataset_needs_a_simple_name(ctl: Ctl):
    (ctl.uploads / "my data.csv").write_text("a,y\n1,2\n")
    r = ctl("dataset", "my data.csv")
    assert r.returncode == 2 and "--name" in r.stderr
    assert ctl("dataset", "my data.csv", "--name", "mydata.csv").returncode == 0


def test_dataset_never_silently_overwrites(ctl: Ctl):
    (ctl.uploads / "d.csv").write_text("a,y\n1,2\n")
    assert ctl("dataset", "d.csv").returncode == 0
    (ctl.uploads / "d.csv").write_text("a,y\n1,2\n")  # same content again: fine
    assert ctl("dataset", "d.csv").returncode == 0
    assert not (ctl.uploads / "d.csv").exists()
    (ctl.uploads / "d.csv").write_text("a,y\n9,9\n")
    assert ctl("dataset", "d.csv").returncode == 3
    assert ctl("dataset", "d.csv", "--replace").returncode == 0
    assert (ctl.data / "d.csv").read_text() == "a,y\n9,9\n"


def test_script_strips_windows_line_endings(ctl: Ctl):
    # With CRLF left in, name is "world\r" and `fi\r` is a syntax error, so
    # nothing below would print. (Text-mode capture would hide a stray \r.)
    script = b'set -eu\r\nname=world\r\nif [ "$name" = world ]; then echo "match pwd=$PWD arg=$1"; fi\r\n'
    (ctl.uploads / "fix.sh").write_bytes(script)
    r = ctl("script", "fix.sh", "hello")
    assert r.returncode == 0, r.stderr
    assert f"match pwd={ctl.repo} arg=hello" in r.stdout


def test_python_scripts_run_through_uv(ctl: Ctl):
    (ctl.uploads / "split.py").write_text("import os, sys\nprint('cwd', os.getcwd(), sys.argv[1:])\n")
    r = ctl("script", "split.py", "--folds", "3")
    assert r.returncode == 0, r.stderr
    assert ctl.uv_args()[:2] == ["run", "python"]
    assert f"cwd {ctl.repo} ['--folds', '3']" in r.stdout


def test_scripts_can_run_as_jobs(ctl: Ctl):
    (ctl.uploads / "slow.sh").write_text("echo step-one\n")
    assert ctl("start", "prep", "script", "slow.sh").returncode == 0
    w = ctl.wait_done("prep")
    assert w.returncode == 0 and "step-one" in w.stdout


def test_bundle_packs_results_datasets_and_job_logs(ctl: Ctl):
    (ctl.repo / "output").mkdir()
    (ctl.repo / "output" / "results.csv").write_text("framework,result\nFLAML,0.9\n")
    (ctl.repo / "input" / "datasets" / "churn").mkdir(parents=True)
    (ctl.repo / "input" / "datasets" / "churn" / "churn.yaml").write_text("- name: churn\n")
    ctl("start", "sweep", "caml", "sweep", "FLAML")
    ctl.wait_done("sweep")
    r = ctl("bundle", "run1")
    assert r.returncode == 0, r.stderr
    info = kv(r.stdout)
    out = ctl.bundles / "run1.tar.gz"
    assert info["bundle"] == str(out)
    assert (out.stat().st_mode & 0o777) == 0o600
    assert info["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        assert not any(m.issym() or m.islnk() for m in tar.getmembers())  # plain files unpack on Windows too
    assert {"run1/output/results.csv", "run1/datasets/churn/churn.yaml", "run1/jobs/sweep.log", "run1/server-info.txt"} <= names
    assert not any(":" in n for n in names)  # Windows can't create files with a colon
    assert ctl("bundle", "run1").returncode == 3


def test_tabpfn_token_needs_a_terminal_and_check_never_prints_it(ctl: Ctl):
    r = ctl("tabpfn-token")
    assert r.returncode == 1
    assert "ssh -t caml-vps camlctl tabpfn-token" in r.stderr
    assert ctl("tabpfn-token", "--check").stdout.strip() == "token-missing"
    r = ctl("tabpfn-token", "--check", extra_env={"TABPFN_TOKEN": "s3cret-value"})
    assert r.stdout.strip() == "token-set"
    assert "s3cret" not in r.stdout + r.stderr


def test_setup_and_update_refuse_safely(ctl: Ctl):
    if os.geteuid() != 0:
        r = ctl("setup")
        assert r.returncode == 1 and "setup needs root" in r.stderr
    r = ctl("update")  # the fake repo has no .git
    assert r.returncode == 1 and "sync_vps.sh" in r.stderr


def test_update_refuses_while_a_job_runs(ctl: Ctl):
    (ctl.repo / ".git").mkdir()
    ctl("start", "long", "caml", "sweep", "FLAML", extra_env={"FAKE_SWEEP_SECS": "60"})
    r = ctl("update")
    assert r.returncode == 3 and "mix revisions" in r.stderr
    ctl("stop", "long", timeout=120)
