"""Describe a dataset without printing its values, and pseudonymize it.

``caml describe-data`` exists for AI agents. Before preparing a benchmark,
an agent has to propose the task (target, task type, columns to leave out,
row structure, metric) and confirm it with the user. To propose it, it needs
the data's shape. But every value it prints lands in the model's context,
and from there at the agent's provider. So this reports the schema and
aggregates only: per column its kind, missing share, distinct count and
flags (identifier, constant, free text, date, possible personal data,
possible leak). It prints no cell values, except the target's class labels
and counts once the target is named, because the user has to confirm those.

``caml anonymize-data`` drops identifying columns and replaces ID columns
that are still needed (for grouping) with salted hashes. The salt is random
and never stored, so the pseudonyms can't be reversed. That removes direct
identifiers. It isn't anonymization in the legal sense: combinations of
ordinary columns (postcode, birth date, job) can still single people out.

Pure pandas/numpy/scikit-learn, no ``caml`` runtime imports beyond
``caml.prepare``, so it's directly unit-testable. The CLI glue is in
``cli.py``.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .prepare import (
    DEFAULT_METRICS,
    PrepareError,
    infer_task_type,
    read_table,
    resolve_column,
)

PLAIN_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
SAMPLE = 2000  # values checked per column for patterns

# Column-name tokens. Split on anything that isn't a letter or digit, and on
# camelCase, so `customerID` -> ["customer", "id"].
ID_TOKENS = {"id", "ids", "uuid", "guid", "key", "pk", "index", "idx", "rowid", "nr", "no"}
TARGET_TOKENS = {"target", "label", "labels", "class", "y", "outcome", "response", "result", "diagnosis",
                 "churn", "churned", "default", "fraud", "survived", "price", "status"}
PERSON_TOKENS = {"first", "last", "full", "sur", "given", "family", "middle", "maiden", "customer", "client",
                 "patient", "user", "employee", "person", "contact", "owner", "member", "student"}
PII_NAME_TOKENS = {
    "email": "an email address", "phone": "a phone number",
    "mobile": "a phone number", "tel": "a phone number", "telephone": "a phone number", "fax": "a phone number",
    "address": "an address", "street": "an address", "addr": "an address", "zip": "a postcode",
    "zipcode": "a postcode", "postcode": "a postcode", "postal": "a postcode", "ssn": "a national ID number",
    "passport": "a passport number", "iban": "a bank account", "dob": "a birth date", "birthdate": "a birth date",
    "birthday": "a birth date", "birth": "a birth date", "ip": "an IP address", "username": "a user name",
    "surname": "a person's name", "firstname": "a person's name",
    "lastname": "a person's name", "fullname": "a person's name", "nationalid": "a national ID number",
}
VALUE_PATTERNS = (
    ("email addresses", re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")),
    ("phone numbers", re.compile(r"^(\+|00|\()\d[\d\s().-]{6,18}\d$|^\d{2,4}[\s-]\d{2,4}[\s-]\d{2,5}$")),
    ("IP addresses", re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")),
    ("web addresses", re.compile(r"^https?://", re.I)),
    ("bank account numbers (IBAN)", re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9 ]{11,30}$")),
)
DATE_PATTERN = re.compile(
    r"^(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})([ T]\d{1,2}:\d{2}(:\d{2})?.*)?$"
)


def _tokens(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    return [t for t in re.split(r"[^a-z0-9]+", spaced.lower()) if t]


def _share(values: pd.Series, pattern: re.Pattern) -> float:
    if values.empty:
        return 0.0
    return float(values.map(lambda v: bool(pattern.match(v))).mean())


def _luhn_share(values: pd.Series) -> float:
    def ok(v: str) -> bool:
        digits = re.sub(r"[\s-]", "", v)
        if not digits.isdigit() or not 13 <= len(digits) <= 19:
            return False
        total = 0
        for i, d in enumerate(reversed(digits)):
            n = int(d) * (2 if i % 2 else 1)
            total += n - 9 if n > 9 else n
        return total % 10 == 0
    return float(values.map(ok).mean()) if not values.empty else 0.0


def _string_sample(series: pd.Series) -> pd.Series:
    values = series.dropna()
    if len(values) > SAMPLE:
        values = values.sample(SAMPLE, random_state=0)
    return values.astype(str).str.strip()


def column_kind(series: pd.Series) -> str:
    """empty, constant, one-value, boolean, integer, numeric, datetime, text or categorical.

    ``one-value`` is one value or empty: whether a row is empty can still carry
    information (and leak the target), so it isn't treated as constant.
    """
    values = series.dropna()
    if values.empty:
        return "empty"
    if values.nunique() == 1:
        return "constant" if len(values) == len(series) else "one-value"
    if pd.api.types.is_bool_dtype(values):
        return "boolean"
    if pd.api.types.is_numeric_dtype(values):
        floats = values.to_numpy(dtype=float)
        return "integer" if np.all(np.isfinite(floats)) and np.all(floats == np.round(floats)) else "numeric"
    if pd.api.types.is_datetime64_any_dtype(values):
        return "datetime"
    text = _string_sample(values)
    if _share(text, DATE_PATTERN) >= 0.9:
        return "datetime"
    if text.str.len().mean() > 30 and values.nunique() > 0.5 * len(values):
        return "text"
    return "categorical"


def pii_hint(name: str, series: pd.Series, kind: str) -> str | None:
    """Why this column may hold personal data, or None. Says what, never the values."""
    tokens = _tokens(name)
    for t in tokens:
        if t in PII_NAME_TOKENS:
            return f"its name suggests {PII_NAME_TOKENS[t]}"
    if "name" in tokens and (len(tokens) == 1 or PERSON_TOKENS & set(tokens)):
        return "its name suggests a person's name"
    if kind in ("categorical", "text"):
        text = _string_sample(series)
        for what, pattern in VALUE_PATTERNS:
            if _share(text, pattern) >= 0.5:
                return f"most values look like {what}"
        if _luhn_share(text) >= 0.5:
            return "most values look like card numbers"
    return None


def _leak_hint(feature: pd.Series, y: pd.Series, task_type: str) -> str | None:
    """A feature that predicts the target (almost) perfectly is usually a leak."""
    if task_type != "regression" and feature.isna().any() and feature.notna().any():
        # e.g. `cancel_date`: filled in exactly for the rows that churned
        present = feature.notna()[y.notna()]
        labels = y.dropna().astype(str)
        if (labels.groupby(present).nunique() == 1).all() and present.nunique() == 2:
            return "whether it's empty matches the target classes exactly"
    mask = feature.notna() & y.notna()
    x, t = feature[mask], y[mask]
    if len(x) < 20 or x.nunique() < 2:
        return None
    if task_type == "regression":
        if pd.api.types.is_numeric_dtype(x) and x.nunique() > 10:
            corr = np.corrcoef(x.to_numpy(dtype=float), t.to_numpy(dtype=float))[0, 1]
            if np.isfinite(corr) and abs(corr) >= 0.99:
                return f"correlates {corr:+.3f} with the target"
        return None
    if pd.api.types.is_numeric_dtype(x) and x.nunique() > 20:
        if task_type == "binary":
            from sklearn.metrics import roc_auc_score
            positive = t.astype(str) == sorted(t.astype(str).unique())[-1]
            auc = roc_auc_score(positive, x.to_numpy(dtype=float))
            if auc >= 0.999 or auc <= 0.001:
                return "separates the target classes perfectly on its own"
        return None
    groups = x.astype(str)
    if len(x) / groups.nunique() >= 5 and (t.astype(str).groupby(groups).nunique() == 1).all():
        return "each of its values occurs with only one target class"
    return None


def _target_candidates(df: pd.DataFrame, kinds: dict[str, str]) -> list[str]:
    usable = [c for c in df.columns if kinds[c] not in ("empty", "constant", "text")]
    named = [c for c in usable if TARGET_TOKENS & set(_tokens(c))]
    last = [df.columns[-1]] if df.columns[-1] in usable else []
    low_card = [c for c in usable if kinds[c] in ("categorical", "boolean") and df[c].nunique() <= 10]
    out: list[str] = []
    for c in named + last + low_card:
        if c not in out:
            out.append(c)
    return out[:3]


def _metric_advice(task_type: str, counts: pd.Series | None) -> tuple[list[str], str | None]:
    metrics = list(DEFAULT_METRICS[task_type])
    if counts is None or counts.empty:
        return metrics, None
    share = counts.iloc[-1] / counts.sum()
    if share < 0.05:
        if task_type == "binary":
            return metrics, ("strong imbalance: consider --metric balacc --metric pr_auc --metric auc, "
                             "or ask which errors cost more")
        return metrics, "strong imbalance: consider --metric balacc --metric logloss"
    return metrics, None


def describe(df: pd.DataFrame, target: str | None = None, *, read_note: str | None = None) -> dict:
    """The report ``caml describe-data`` prints. No cell values except the named target's labels."""
    if df.columns.duplicated().any():
        dupes = sorted(set(df.columns[df.columns.duplicated()].astype(str)))
        raise PrepareError(f"Duplicate column names: {', '.join(dupes)}. Rename them first.")
    df.columns = [str(c) for c in df.columns]
    n = len(df)
    if n == 0:
        raise PrepareError("The file has a header but no rows.")
    if target is not None:
        target = resolve_column(df.columns, target, "Target column")

    kinds = {c: column_kind(df[c]) for c in df.columns}
    columns, suggest_drop, ask = [], [], []
    for i, c in enumerate(df.columns, start=1):
        s = df[c]
        kind = kinds[c]
        missing = float(s.isna().mean())
        distinct = int(s.nunique())
        flags: list[str] = []
        notes: list[str] = []
        tokens = set(_tokens(c))
        unique_per_row = distinct == n and missing == 0
        if c == target:
            flags.append("target")
        elif kind in ("empty", "constant"):
            flags.append(kind)
            suggest_drop.append(c)
        else:
            if unique_per_row and kind in ("integer", "categorical") and (
                ID_TOKENS & tokens or kind != "integer"
                or (s.is_monotonic_increasing or s.is_monotonic_decreasing)
            ):
                flags.append("id-like")
                notes.append("unique on every row: teaches nothing, drop it")
                suggest_drop.append(c)
            elif ID_TOKENS & tokens and kind in ("integer", "categorical") and 1 < distinct < n:
                flags.append("group-id?")
                notes.append(f"{distinct} values over {n} rows: several rows share an ID; ask whether they "
                             "must stay in the same fold")
                ask.append(f"rows sharing {c!r}: independent, or grouped?")
            pii = pii_hint(c, s, kind)
            if pii:
                flags.append("pii?")
                notes.append(f"possible personal data ({pii})")
                if c not in suggest_drop:
                    suggest_drop.append(c)
            if kind == "datetime":
                flags.append("date")
                notes.append("a date: rows ordered in time need a time-based split; otherwise derive "
                             "parts (year, month, weekday) or drop it")
                ask.append(f"is {c!r} a time order the split must respect?")
            if kind == "text":
                flags.append("free-text")
                notes.append("long, mostly unique text: frameworks treat it as a huge category")
                ask.append(f"keep the free text in {c!r}? Frameworks treat it as a huge category; dropping it is usual")
            if kind == "categorical" and distinct > 50 and distinct > 0.5 * n and "id-like" not in flags:
                flags.append("high-cardinality")
            if missing > 0.5:
                flags.append("mostly-missing")
        columns.append({
            "number": i, "name": c, "kind": kind, "missing": round(missing, 4), "distinct": distinct,
            "plain_name": bool(PLAIN_NAME.match(c)), "flags": flags, "notes": notes,
        })

    report: dict = {
        "rows": n,
        "columns": len(df.columns),
        "read_as": read_note,
        "duplicate_rows": int(df.duplicated().sum()),
        "values_shown": "none: names, kinds and counts only" + ("; the target's labels" if target else ""),
        "column_list": columns,
        "names_needing_numbers": [c["number"] for c in columns if not c["plain_name"]],
    }

    candidates = []
    for c in ([target] if target else _target_candidates(df, kinds)):
        y = df[c].dropna()
        try:
            task_type, reason = infer_task_type(y)
        except PrepareError as e:
            task_type, reason = None, str(e)
        candidates.append({"name": c, "number": list(df.columns).index(c) + 1, "task_type": task_type,
                           "reason": reason})
    report["target_candidates"] = candidates

    if target:
        y = df[target]
        info = candidates[0]
        report["target"] = {"name": target, "number": info["number"], "missing_rows": int(y.isna().sum()),
                            "task_type_guess": info["task_type"], "reason": info["reason"]}
        counts = None
        if info["task_type"] in ("binary", "multiclass"):
            counts = y.dropna().astype(str).value_counts()
            report["target"]["classes"] = {str(k): int(v) for k, v in counts.head(20).items()}
            report["target"]["class_count"] = int(len(counts))
            report["target"]["smallest_class_share"] = round(float(counts.iloc[-1] / counts.sum()), 4)
        if info["task_type"]:
            metrics, advice = _metric_advice(info["task_type"], counts)
            report["target"]["metrics_default"] = metrics
            report["target"]["metric_advice"] = advice
            for col in columns:
                if col["name"] == target or col["kind"] in ("empty", "constant"):
                    continue
                hint = _leak_hint(df[col["name"]], y, info["task_type"])
                if not hint and target.lower() in col["name"].lower() and len(target) >= 3:
                    hint = "its name contains the target's name"
                if hint:
                    col["flags"].append("leak?")
                    col["notes"].append(f"possible leak: {hint}; ask whether it's known before the outcome")
                    ask.append(f"is {col['name']!r} known before the outcome, or recorded after it?")
    if report["duplicate_rows"]:
        ask.append(f"{report['duplicate_rows']} exact duplicate rows: real repeats, or a data error? "
                   "(duplicates in train and test folds inflate scores)")
    report["suggest_drop"] = suggest_drop
    report["ask_user"] = ask
    return report


def describe_file(path: str | Path, target: str | None = None) -> dict:
    path = Path(path).expanduser().resolve()
    notes: list[str] = []
    df = read_table(path, notes)
    if path.suffix.lower() == ".csv" and not notes:
        notes.append("Read as comma-separated.")
    note = " ".join(n.removeprefix("Read as ").rstrip(".") for n in notes) or None
    report = describe(df, target, read_note=note)
    return {"file": str(path), **report}


def _ref(col: dict) -> str:
    return col["name"] if col["plain_name"] else str(col["number"])


def format_report(r: dict) -> str:
    """Text for agents: `key: value` lines, a column table, then what to ask."""
    out = [f"file: {r['file']}", f"rows: {r['rows']}", f"columns: {r['columns']}"]
    if r.get("read_as"):
        out.append(f"read_as: {r['read_as']}")
    out.append(f"duplicate_rows: {r['duplicate_rows']}")
    out.append(f"values_shown: {r['values_shown']}")
    out.append("")
    cols = r["column_list"]
    width = min(max([len(c["name"]) for c in cols] + [6]), 40)
    out.append(f"{'#':>4}  {'column':<{width}}  {'kind':<11}  {'missing':>7}  {'distinct':>8}  flags")
    for c in cols:
        out.append(f"{c['number']:>4}  {c['name']:<{width}}  {c['kind']:<11}  {c['missing']:>7.1%}  "
                   f"{c['distinct']:>8}  {', '.join(c['flags'])}")
    noted = [c for c in cols if c["notes"]]
    if noted:
        out.append("")
        out.append("notes:")
        for c in noted:
            for note in c["notes"]:
                out.append(f"- #{c['number']} {c['name']}: {note}")
    if r["names_needing_numbers"]:
        out.append("")
        out.append("names_needing_numbers: " + ", ".join(f"#{n}" for n in r["names_needing_numbers"])
                   + " (spaces or symbols: pass these by number, e.g. --drop "
                   + str(r["names_needing_numbers"][0]) + ")")
    out.append("")
    if "target" in r:
        t = r["target"]
        out.append(f"target: {t['name']} (#{t['number']})")
        out.append(f"task_type_guess: {t['task_type_guess'] or 'none'} ({t['reason']})")
        if t["missing_rows"]:
            out.append(f"target_missing_rows: {t['missing_rows']} (prepare-data drops them)")
        if "classes" in t:
            shown = ", ".join(f"{k} {v}" for k, v in t["classes"].items())
            more = f" (+{t['class_count'] - len(t['classes'])} more)" if t["class_count"] > len(t["classes"]) else ""
            out.append(f"classes: {shown}{more}")
            out.append(f"smallest_class_share: {t['smallest_class_share']:.1%}")
        if t.get("metrics_default"):
            out.append(f"metric_default: {t['metrics_default'][0]} (also scored: {', '.join(t['metrics_default'][1:])})")
        if t.get("metric_advice"):
            out.append(f"metric_advice: {t['metric_advice']}")
    else:
        cands = "; ".join(
            f"{c['name']} (#{c['number']}: {c['task_type'] or 'unusable'}, {c['reason']})" for c in r["target_candidates"]
        )
        out.append(f"target_candidates: {cands or 'none found: ask the user'}")
    drop_refs = [_ref(c) for c in cols if c["name"] in r["suggest_drop"]]
    out.append("suggest_drop: " + (" ".join(f"--drop {d}" for d in drop_refs) if drop_refs else "none"))
    if r["ask_user"]:
        out.append("ask_user:")
        out.extend(f"- {q}" for q in r["ask_user"])
    out.append("")
    if "target" in r:
        t = r["target"]
        ref = t["name"] if PLAIN_NAME.match(t["name"]) else str(t["number"])
        out.append("next: confirm the task with the user (target, task type, columns, row structure, metric), "
                   f"then: caml prepare-data {r['file']} --target {ref} "
                   + " ".join(f"--drop {d}" for d in drop_refs) + " --name NAME --folds 5")
    else:
        out.append(f"next: caml describe-data {r['file']} --target COLUMN   (after asking the user which column "
                   "to predict; the candidates above are guesses)")
    return "\n".join(line.rstrip() for line in out)


def _pseudonym(key: bytes, value) -> str:
    return "h_" + hmac.new(key, str(value).encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def anonymize_file(path: str | Path, *, drop: Sequence[str] = (), hash_columns: Sequence[str] = (),
                   out: str | Path | None = None, delete_original: bool = False) -> dict:
    """Drop and pseudonymize columns; return `key: value` facts (no values)."""
    path = Path(path).expanduser().resolve()
    if not drop and not hash_columns:
        raise PrepareError("Name at least one column with --drop or --hash.")
    df = read_table(path)
    df.columns = [str(c) for c in df.columns]
    drop = list(dict.fromkeys(resolve_column(df.columns, c, "--drop column") for c in drop))
    hashed = list(dict.fromkeys(resolve_column(df.columns, c, "--hash column") for c in hash_columns))
    both = set(drop) & set(hashed)
    if both:
        raise PrepareError(f"Column(s) {', '.join(sorted(both))} can't be both dropped and hashed.")
    if len(drop) >= len(df.columns):
        raise PrepareError("That would drop every column.")
    is_parquet = path.suffix.lower() in (".parquet", ".pq")
    out_path = Path(out).expanduser().resolve() if out else path.with_name(
        f"{path.stem}-anon{'.parquet' if is_parquet else '.csv'}")
    if out_path == path:
        raise PrepareError("--out must differ from the input file.")
    if out_path.exists():
        raise PrepareError(f"{out_path} already exists; pick another --out or delete it first.")

    key = os.urandom(32)  # never stored: the pseudonyms can't be reversed
    df = df.drop(columns=drop)
    distinct = {}
    for c in hashed:
        mask = df[c].notna()
        df[c] = df[c].astype(object)
        df.loc[mask, c] = df.loc[mask, c].map(lambda v: _pseudonym(key, v))
        distinct[c] = int(df[c].nunique())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() in (".parquet", ".pq"):
        df.to_parquet(out_path, index=False)
    else:
        df.to_csv(out_path, index=False)
    os.chmod(out_path, 0o600)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()

    facts = {
        "wrote": str(out_path),
        "rows": len(df),
        "columns": len(df.columns),
        "dropped": ", ".join(drop) or "none",
        "hashed": ", ".join(f"{c} ({distinct[c]} distinct values, still distinct)" for c in hashed) or "none",
        "pseudonyms": "salted SHA-256 with a random key that wasn't stored: they can't be reversed" if hashed else "none",
        "sha256": digest,
    }
    if delete_original:
        removed = []
        for p in (path, path.with_name(path.name + ".orig")):
            if p.exists():
                p.unlink()
                removed.append(str(p))
        facts["deleted"] = ", ".join(removed)
    facts["note"] = ("direct identifiers are gone; combinations of other columns (postcode, birth date, job) can "
                     "still single people out")
    facts["next"] = f"caml describe-data {out_path}"
    return facts
