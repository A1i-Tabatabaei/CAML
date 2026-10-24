"""Tests for caml.leaderboard (`caml leaderboard`): ranking direction,
natural-direction metric display, latest-row deduplication, failure
accounting, and the text/Markdown formatting."""

from __future__ import annotations

import math

import pandas as pd

from caml.leaderboard import format_board, latest_per_fold, leaderboard


def _row(fw, task, fold, result, metric="auc", utc="2026-10-24T10:00:00", info=None, constraint="test",
         type_="binary", train=60.0):
    return dict(framework=fw, task=task, constraint=constraint, fold=fold, result=result, metric=metric,
                utc=utc, info=info, type=type_, training_duration=train)


def test_ranks_by_mean_higher_is_better():
    df = pd.DataFrame([
        _row("A", "t", 0, 0.80), _row("A", "t", 1, 0.84),
        _row("B", "t", 0, 0.90), _row("B", "t", 1, 0.92),
    ])
    (board,) = leaderboard(df)
    assert [r["framework"] for r in board["rows"]] == ["B", "A"]
    assert board["rows"][0]["rank"] == 1 and math.isclose(board["rows"][0]["mean"], 0.91)
    assert board["metric"] == "auc" and board["higher_is_better"]


def test_loss_metrics_shown_in_natural_direction():
    df = pd.DataFrame([
        _row("A", "r", 0, -40.0, metric="neg_rmse", type_="regression"),
        _row("B", "r", 0, -50.0, metric="neg_rmse", type_="regression"),
    ])
    (board,) = leaderboard(df)
    assert board["metric"] == "rmse" and not board["higher_is_better"]
    assert [(r["framework"], r["mean"]) for r in board["rows"]] == [("A", 40.0), ("B", 50.0)]


def test_latest_row_per_fold_wins():
    df = pd.DataFrame([
        _row("A", "t", 0, 0.10, utc="2026-10-01T00:00:00"),
        _row("A", "t", 0, 0.90, utc="2026-10-02T00:00:00"),
    ])
    assert latest_per_fold(df)["result"].tolist() == [0.90]
    (board,) = leaderboard(df)
    assert board["rows"][0]["folds_total"] == 1


def test_failed_folds_are_counted_and_all_failed_is_unranked():
    df = pd.DataFrame([
        _row("A", "t", 0, 0.8), _row("A", "t", 1, math.nan, info="MemoryError"),
        _row("C", "t", 0, math.nan, info="ImportError: boom"),
    ])
    (board,) = leaderboard(df)
    a, c = board["rows"]
    assert (a["framework"], a["folds_ok"], a["folds_total"], a["rank"]) == ("A", 1, 2, 1)
    assert a["error"] == "MemoryError"
    assert (c["framework"], c["rank"], c["error"]) == ("C", None, "ImportError: boom")


def test_one_board_per_task_and_constraint():
    df = pd.DataFrame([_row("A", "t1", 0, 0.8), _row("A", "t2", 0, 0.7), _row("A", "t1", 0, 0.6, constraint="1h8c")])
    assert [(b["task"], b["constraint"]) for b in leaderboard(df)] == [("t1", "1h8c"), ("t1", "test"), ("t2", "test")]


def test_formatting_text_and_markdown():
    df = pd.DataFrame([_row("A", "t", 0, 0.8), _row("B", "t", 0, math.nan, info="Killed\nby OOM")])
    (board,) = leaderboard(df)
    text = format_board(board)
    assert "metric auc: higher is better" in text and "Killed by OOM" in text
    md = format_board(board, markdown=True)
    assert md.splitlines()[2].startswith("| rank | framework |") and "| 1 | A | 0.8000 |" in md
