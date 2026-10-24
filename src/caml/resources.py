# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

"""
**resources** module exposes a singleton ``Resources`` instance providing
easy access to app configuration properties, plus handy methods to access
benchmark/constraint definitions and (via ``caml.frameworks.registry``)
framework definitions.

Rewritten from AMLB's ``amlb/resources.py``: the framework-catalogue half
(``framework_definition``/``_frameworks``, previously backed by
``resources/frameworks.yaml``) is replaced by directory-based discovery in
``caml.frameworks.registry`` (see that module's docstring for why). The
AWS-only ``ec2_instance_type``/``ec2_volume_type`` task defaulting in
``_validate_task`` is dropped entirely — CAML has no AWS runner.
"""

from __future__ import annotations

import copy
import logging
import random
import re
import sys
from functools import cache, cached_property
from pathlib import Path

from .__version__ import __version__
from .benchmarks.parser import benchmark_load
from .definitions import TaskConstraint
from .frameworks.registry import FrameworkDefinition, load_framework_definition
from .utils import Namespace, normalize_path, run_cmd, str_sanitize, touch
from .utils.config import config_load

log = logging.getLogger(__name__)


class Resources:
    @staticmethod
    def _normalize(config: Namespace, replace=None):
        def nz_path(path):
            if replace is not None:
                path = path.format(**replace)
            return normalize_path(path)

        normalized = copy.copy(config)
        for k, v in config:
            if isinstance(v, Namespace):
                normalized[k] = Resources._normalize(v, replace=replace)
            elif re.search(r"_(dir|file|cmd)s?$", k):
                normalized[k] = (
                    [nz_path(p) for p in v] if isinstance(v, list) else nz_path(v)
                )
        return normalized

    def __init__(self, config: Namespace):
        self._config = config
        common_dirs = dict(
            input=normalize_path(config.input_dir),
            output=normalize_path(config.output_dir),
            user=normalize_path(config.user_dir) if config.user_dir else None,
            root=normalize_path(config.root_dir),
        )
        self.config = Resources._normalize(config, replace=common_dirs)
        self.config.common_dirs = common_dirs
        log.debug("Using config:\n%s", self.config)

        if common_dirs["user"]:
            sys.path.append(common_dirs["user"])

        # frameworks/ lives at the repo root, as a sibling of src/ and
        # resources/ — add it to sys.path so `import frameworks.<Name>`
        # resolves at run time (see BenchmarkTask.run / caller.py).
        sys.path.append(common_dirs["root"])

    @property
    def frameworks_root(self) -> Path:
        return Path(self.config.common_dirs["root"]) / "frameworks"

    @cached_property
    def git_info(self):
        def git(cmd, defval=None):
            try:
                return run_cmd(f"git {cmd}", _log_level_=logging.DEBUG)[0].strip()
            except Exception:
                return defval

        na = "NA"
        git_version = git("--version")
        is_repo = git("rev-parse") is not None

        if git_version and is_repo:
            repo = git("remote get-url origin", na)
            branch = git("rev-parse --abbrev-ref HEAD", na)
            commit = git("rev-parse HEAD", na)
            tags = git("tag --points-at HEAD", "").splitlines()
            status = git("status -b --porcelain", "").splitlines()
        else:
            repo = branch = commit = na
            tags = status = []
            # No .git (e.g. a VPS checkout delivered as a `git archive` by
            # scripts/provision_vps.sh / sync_vps.sh): fall back to the
            # REVISION file those scripts write, so results stay traceable to
            # an exact commit instead of reading "NA".
            rev = self._revision_file()
            if rev:
                branch = rev.get("branch", na)
                commit = rev.get("commit", na)
                if rev.get("dirty") == "1":
                    commit += "+worktree"
        return Namespace(repo=repo, branch=branch, commit=commit, tags=tags, status=status)

    def _revision_file(self) -> dict | None:
        path = Path(self.config.common_dirs["root"]) / "REVISION"
        try:
            lines = path.read_text().splitlines()
        except OSError:
            return None
        return dict(line.split("=", 1) for line in lines if "=" in line)

    @cached_property
    def app_version(self):
        """CAML's version plus the code revision behind a result, e.g.
        ``1.0.0 [main, 3eb1cf7]``, with ``+worktree`` when uncommitted
        changes were run (git checkout) or deployed (REVISION ``dirty=1``).

        AMLB only appended the revision when ``__version__ == "dev"``;
        CAML's version was ``0.1.0-dev``, so before 2026-10-24 every
        results.csv row said just ``0.1.0-dev`` and no result was traceable
        to a commit, REVISION file or not.
        """
        g = self.git_info
        if not g.commit or g.commit == "NA":
            return __version__
        sha, _, suffix = g.commit.partition("+")
        dirty = bool(suffix) or any(not line.startswith("##") for line in g.status)
        return f"{__version__} [{g.branch}, {sha[:7]}{'+worktree' if dirty else ''}]"

    def seed(self, fold=None):
        if isinstance(fold, int) and str(self.config.seed).lower() in ["auto"]:
            return fold + self._seed
        else:
            return self._seed

    @cached_property
    def _seed(self):
        if str(self.config.seed).lower() in ["none", ""]:
            return None
        elif str(self.config.seed).lower() in ["auto"]:
            return random.randint(1, (1 << 31) - 1)
        else:
            return self.config.seed

    def framework_definition(self, name: str) -> tuple[FrameworkDefinition, str]:
        """:return: (framework definition, resolved name)"""
        framework = load_framework_definition(name, self.frameworks_root)
        return framework, framework.name

    @cache
    def constraint_definition(self, name: str) -> TaskConstraint:
        constraint = self._constraints[name.lower()]
        if not constraint:
            raise ValueError(
                "Incorrect constraint definition `{}`: not listed in {}.".format(
                    name, self.config.benchmarks.constraints_file
                )
            )
        return TaskConstraint(**Namespace.dict(constraint))

    @cached_property
    def _constraints(self):
        constraints_file = self.config.benchmarks.constraints_file
        log.info("Loading benchmark constraint definitions from %s.", constraints_file)
        if not isinstance(constraints_file, list):
            constraints_file = [constraints_file]

        constraints = Namespace()
        for cf in constraints_file:
            constraints += config_load(cf)

        for name, c in constraints:
            c.name = str_sanitize(name)

        constraints_lookup = Namespace()
        for name, c in constraints:
            constraints_lookup[name.lower()] = c
        return constraints_lookup

    def benchmark_definition(self, name: str, defaults: TaskConstraint | None = None):
        return self._benchmark_definition(name, self.config, defaults)

    def _benchmark_definition(
        self, name: str, config_: Namespace, defaults: TaskConstraint | None = None
    ):
        import dataclasses

        file_defaults, tasks, benchmark_path, benchmark_name = benchmark_load(
            name, config_.benchmarks.definition_dir
        )
        if defaults is not None:
            defaults = Namespace(**dataclasses.asdict(defaults))
        defaults_ = Namespace.merge(
            defaults, file_defaults, Namespace(name="__defaults__")
        )
        for task in tasks:
            task |= defaults_
            Resources._validate_task(task, config_)

        Resources._validate_task(defaults, config_, lenient=True)
        defaults_.enabled = False
        tasks.append(defaults_)
        log.debug("Available task definitions:\n%s", tasks)
        return tasks, benchmark_name, benchmark_path

    @staticmethod
    def _validate_task(task: Namespace, config_: Namespace, lenient: bool = False):
        missing = []
        for conf in ["name"]:
            if task[conf] is None:
                missing.append(conf)
        if not lenient and len(missing) > 0:
            raise ValueError(
                "{missing} mandatory properties are missing in task definition {taskdef}.".format(
                    missing=missing, taskdef=task
                )
            )

        for conf in [
            "max_runtime_seconds",
            "cores",
            "folds",
            "max_mem_size_mb",
            "min_vol_size_mb",
            "quantile_levels",
        ]:
            if task[conf] is None:
                task[conf] = config_.benchmarks.defaults[conf]

        if task["metric"] is None:
            task["metric"] = None

        conf = "id"
        if task[conf] is None:
            task[conf] = (
                "openml.org/t/{}".format(task.openml_task_id)
                if task["openml_task_id"] is not None
                else "openml.org/d/{}".format(task.openml_dataset_id)
                if task["openml_dataset_id"] is not None
                else (
                    (
                        task.dataset["id"]
                        if isinstance(task.dataset, (dict, Namespace))
                        else task.dataset
                        if isinstance(task.dataset, str)
                        else None
                    )
                    or task.name
                )
                if task["dataset"] is not None
                else None
            )
            if not lenient and task[conf] is None:
                raise ValueError(
                    "task definition must contain an ID or one property "
                    "among ['openml_task_id', 'dataset'] to create an ID, "
                    "but task definition is {task}".format(task=str(task))
                )


__INSTANCE__: Resources | None = None


def from_configs(*configs: Namespace):
    global __INSTANCE__
    __INSTANCE__ = Resources(Namespace.merge(*configs, deep=True))
    return __INSTANCE__


def get() -> Resources:
    if __INSTANCE__ is None:
        raise RuntimeError("No configuration has been loaded yet.")
    return __INSTANCE__


def config():
    if __INSTANCE__ is None:
        raise RuntimeError("No configuration has been loaded yet.")
    return __INSTANCE__.config


def output_dirs(root, session=None, subdirs=None, create=False):
    root = root if root is not None else "."
    if create and not Path(root).exists():
        touch(root, as_dir=True)

    dirs = Namespace(
        root=root, session=str(Path(root) / session) if session is not None else root
    )

    subdirs = [] if subdirs is None else [subdirs] if isinstance(subdirs, str) else subdirs

    for d in subdirs:
        dirs[d] = str(Path(dirs.session) / d)
        if create and not Path(dirs[d]).exists():
            touch(dirs[d], as_dir=True)
    return dirs
