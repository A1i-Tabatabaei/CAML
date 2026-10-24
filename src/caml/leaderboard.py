"""Per-task framework ranking from ``output/results.csv`` (``caml leaderboard``).

``caml compare`` answers "is one framework significantly better *across
datasets*" and needs 2+ tasks. Someone benchmarking frameworks on their own
single dataset needs the other view: per task, every framework ranked by
its mean primary metric over the folds, with the spread, how many folds
succeeded, and what each run cost. This module builds that table.

Reads ``result`` (direction-normalized to higher-is-better by
``TaskResult.compute_score()``: losses are stored negated under a ``neg_``
metric name) for ranking, and reports the metric in its natural direction
(``neg_rmse`` -0.42 is shown as rmse 0.42, lower is better).

``results.csv`` is append-only across sessions, so repeated runs of the same
(framework, task, constraint, fold) are deduplicated here, keeping the
latest row by ``utc``. A row with an empty ``result`` is a failed job
(``caml run --keep-going`` / ``caml sweep`` record those with the error in
``info``).

Pure pandas, no ``caml.*`` imports, so it's directly unit-testable.
"""

from __future__ import annotations

import math

import pandas as pd

KEY = ["framework", "task", "constraint", "fold"]


def latest_per_fold(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the newest row for each (framework, task, constraint, fold)."""
    if df.empty:
        return df
    order = df.sort_values("utc", kind="stable") if "utc" in df.columns else df
    return order.drop_duplicates(subset=KEY, keep="last").reset_index(drop=True)


def _natural(metric: str, value: float) -> tuple[str, float]:
    if isinstance(metric, str) and metric.startswith("neg_"):
        return metric[4:], -value
    return metric, value


def leaderboard(df: pd.DataFrame) -> list[dict]:
    """One entry per (task, constraint): its metric, and frameworks ranked best-first.

    Each framework row has ``mean``/``std`` (natural direction), ``folds_ok``,
    ``folds_total``, ``train_s`` (mean training duration of successful folds),
    ``rank`` (``None`` when every fold failed) and ``error`` (the most recent
    failure message, if any fold failed).
    """
    df = latest_per_fold(df)
    boards = []
    for (task, constraint), group in df.groupby(["task", "constraint"], sort=True):
        metrics = group["metric"].dropna()
        metric = str(metrics.mode().iat[0]) if not metrics.empty else "?"
        natural_metric, _ = _natural(metric, 0.0)
        rows = []
        for framework, fw_rows in group.groupby("framework", sort=True):
            fw_ok = fw_rows[fw_rows["result"].notna()]
            failed = fw_rows[fw_rows["result"].isna()]
            score = float(fw_ok["result"].mean()) if not fw_ok.empty else math.nan
            std = float(fw_ok["result"].std(ddof=1)) if len(fw_ok) > 1 else math.nan
            error = None
            if not failed.empty:
                info = failed["info"].dropna() if "info" in failed.columns else pd.Series(dtype=str)
                error = str(info.iat[-1]) if not info.empty else "failed (no error message recorded)"
            rows.append({
                "framework": framework,
                "score": score,  # higher is better, used for ranking only
                "mean": _natural(metric, score)[1] if not math.isnan(score) else math.nan,
                "std": std,
                "folds_ok": int(len(fw_ok)),
                "folds_total": int(len(fw_rows)),
                "train_s": float(fw_ok["training_duration"].mean()) if "training_duration" in fw_ok and not fw_ok.empty else math.nan,
                "error": error,
            })
        ranked = sorted(rows, key=lambda r: (math.isnan(r["score"]), -r["score"] if not math.isnan(r["score"]) else 0, r["framework"]))
        rank = 0
        for r in ranked:
            r["rank"] = None if math.isnan(r["score"]) else (rank := rank + 1)
        task_type = group["type"].dropna().iat[0] if "type" in group and group["type"].notna().any() else "?"
        boards.append({
            "task": task,
            "constraint": constraint,
            "type": task_type,
            "metric": natural_metric,
            "higher_is_better": not str(metric).startswith("neg_"),
            "rows": ranked,
        })
    return boards


def _fmt(value: float, spec: str = "{:.4f}") -> str:
    return "-" if value is None or (isinstance(value, float) and math.isnan(value)) else spec.format(value)


def format_board(board: dict, markdown: bool = False) -> str:
    direction = "higher is better" if board["higher_is_better"] else "lower is better"
    title = (f"{board['task']}  ({board['type']}, constraint {board['constraint']}, "
             f"metric {board['metric']}: {direction})")
    header = ["rank", "framework", f"{board['metric']} mean", "std", "folds ok", "train s (mean)"]
    body = [
        [
            str(r["rank"]) if r["rank"] else "-",
            r["framework"],
            _fmt(r["mean"]),
            _fmt(r["std"]),
            f"{r['folds_ok']}/{r['folds_total']}",
            _fmt(r["train_s"], "{:.0f}"),
        ]
        for r in board["rows"]
    ]
    failures = [r for r in board["rows"] if r["error"]]
    if markdown:
        out = [f"**{title}**", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        out += ["| " + " | ".join(row) + " |" for row in body]
        if failures:
            out.append("")
            out += [f"- {r['framework']}: {r['folds_total'] - r['folds_ok']} failed fold(s), last error: `{_one_line(r['error'])}`" for r in failures]
        return "\n".join(out)
    widths = [max(len(h), *(len(row[i]) for row in body)) for i, h in enumerate(header)]
    line = lambda cells: "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()  # noqa: E731
    out = [title, line(header), line(["-" * w for w in widths]), *(line(row) for row in body)]
    if failures:
        out.append("")
        out += [f"  {r['framework']}: {r['folds_total'] - r['folds_ok']} failed fold(s); last error: {_one_line(r['error'])}" for r in failures]
    return "\n".join(out)


def _one_line(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."
