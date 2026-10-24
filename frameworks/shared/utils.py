# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

"""Utilities importable from *inside* a framework's isolated venv.

This module runs as the framework's own Python interpreter (see
``../shared/callee.py`` and each framework's ``exec.py``), not the
orchestrator's. ``caml`` isn't pip-installed into per-framework venvs —
``caller.py::run_in_venv`` puts CAML's ``src/`` directory on the
subprocess's ``PYTHONPATH``, so ``caml.utils`` imports using *this*
venv's own numpy/pandas/etc, preserving isolation while sharing code.

Trimmed from AMLB's ``frameworks/shared/utils.py``: dropped the unused
``load_module``/``load_amlb_module`` machinery (confirmed dead — no
framework's ``exec.py`` in the AMLB reference tree calls it; every one
just does ``from frameworks.shared.utils import Timer, ...``).
"""

import logging
import os
import sys

import pandas as pd


def setup_logger():
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logging.basicConfig(handlers=[console])
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    trace_level = os.environ.get("CAML_LOG_TRACE")
    if trace_level:
        logging.TRACE = int(trace_level)


setup_logger()

__no_export = set(dir())  # all variables defined above this are not exported


def load_timeseries_dataset(dataset):
    # Ensure that id_column is loaded as string to avoid incorrect sorting
    train_data = pd.read_csv(
        dataset.train_path,
        dtype={dataset.id_column: str},
        parse_dates=[dataset.timestamp_column],
    )
    test_data = pd.read_csv(
        dataset.test_path,
        dtype={dataset.id_column: str},
        parse_dates=[dataset.timestamp_column],
    )
    return train_data, test_data


from caml.utils import *  # noqa: E402, F403

__all__ = [s for s in dir() if not s.startswith("_") and s not in __no_export]
