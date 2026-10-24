# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

from __future__ import annotations

import logging
import re
from typing import cast

import openml
import pandas as pd
import requests
from openml import OpenMLTask, OpenMLDataset

from caml.utils import Namespace, str_sanitize


log = logging.getLogger(__name__)

# openml-python's own HTTP layer (openml._api_calls) never passes a
# `timeout=` to `requests`, and an absent timeout means "wait forever" --
# confirmed empirically (2026-07-30) that `socket.setdefaulttimeout()`
# does NOT rescue this (a hung local-socket test proved requests/urllib3
# ignores the socket-level default when no explicit `timeout=` kwarg is
# given). During the real OpenML outage (see STATUS.md's Notes), one call
# sat silent for ~53 minutes before the gateway itself returned a 504.
# Patching `requests.Session.request` is the standard workaround the
# `requests` maintainers themselves point to, since the library has no
# built-in way to set a process-wide default
# (https://github.com/psf/requests/issues/3070). This module is
# orchestrator-only -- never imported inside a framework's isolated
# subprocess venv (see frameworks/shared/callee.py, which only imports
# from caml.utils) -- so patching here can't break a framework venv that
# lacks `requests`.
_ORIGINAL_SESSION_REQUEST = requests.Session.request


def install_default_http_timeout(seconds: float = 120) -> None:
    """Make `requests.Session` calls fail after `seconds` of silence
    instead of hanging forever, unless the caller already set a timeout.

    `seconds` bounds each connect attempt / read gap, not total request
    wall-clock time -- a slow-but-steadily-progressing download is not
    affected, only a connection that goes completely silent (the actual
    failure mode of the outage above).
    """

    def _request_with_default_timeout(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = seconds
        return _ORIGINAL_SESSION_REQUEST(self, method, url, **kwargs)

    requests.Session.request = _request_with_default_timeout


install_default_http_timeout()


def is_openml_benchmark(benchmark: str) -> bool:
    """Check if 'benchmark' is a valid identifier for an openml task or suite."""
    return re.match(r"(openml|test\.openml)/[st]/\d+", benchmark) is not None


def load_oml_benchmark(benchmark: str) -> tuple[str, str | None, list[Namespace]]:
    """Loads benchmark defined by openml suite or task, from openml/s/X or openml/t/Y."""
    domain, oml_type, oml_id_str = benchmark.split("/")
    try:
        oml_id = int(oml_id_str)
    except ValueError:
        raise ValueError(
            f"Could not convert OpenML id {oml_id_str!r} in {benchmark!r} to integer."
        )

    if domain == "test.openml":
        log.debug("Setting openml server to the test server.")
        openml.config.server = "https://test.openml.org/api/v1/xml"

    if openml.config.retry_policy != "robot":
        log.debug(
            "Setting openml retry_policy from '%s' to 'robot'."
            % openml.config.retry_policy
        )
        openml.config.set_retry_policy("robot")

    if oml_type == "t":
        tasks = load_openml_task_as_definition(domain, oml_id)
    elif oml_type == "s":
        tasks = load_openml_tasks_from_suite(domain, oml_id)
    else:
        raise ValueError(f"The oml_type is {oml_type} but must be 's' or 't'")
    # The first argument needs to remain parsable further in the pipeline as is
    # The second argument is path, the benchmark does not exist on disk
    return benchmark, None, tasks


def load_openml_tasks_from_suite(domain: str, oml_id: int) -> list[Namespace]:
    log.info("Loading openml suite %s.", oml_id)
    suite = openml.study.get_suite(oml_id)
    # Here we know the (task, dataset) pairs so only download dataset meta-data is sufficient
    tasks = []
    datasets = cast(
        pd.DataFrame,
        openml.datasets.list_datasets(data_id=suite.data, output_format="dataframe"),
    )
    datasets.set_index("did", inplace=True)
    for tid, did in zip(cast(list[int], suite.tasks), cast(list[int], suite.data)):
        tasks.append(
            Namespace(
                name=str_sanitize(datasets.loc[did]["name"]),
                description=f"{domain}/d/{did}",
                openml_task_id=tid,
                id="{}.org/t/{}".format(domain, tid),
            )
        )
    return tasks


def load_openml_task_as_definition(domain: str, oml_id: int) -> list[Namespace]:
    log.info("Loading openml task %s.", oml_id)
    task, data = load_openml_task_and_data(oml_id)
    return [
        Namespace(
            name=str_sanitize(data.name),
            description=data.description,
            openml_task_id=task.id,
            id="{}.org/t/{}".format(domain, task.id),
        )
    ]


def load_openml_task_and_data(
    task_id: int, with_data: bool = False
) -> tuple[OpenMLTask, OpenMLDataset]:
    task = openml.tasks.get_task(task_id, download_data=False, download_qualities=False)
    data = openml.datasets.get_dataset(
        task.dataset_id, download_data=with_data, download_qualities=False
    )
    return task, data
