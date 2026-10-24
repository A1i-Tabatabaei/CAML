"""Tests for caml.describe: `caml describe-data` (the schema and flags an agent
needs to propose a task, without the data's values) and `caml anonymize-data`
(drop and pseudonymize identifying columns).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

from caml.describe import anonymize_file, column_kind, describe, describe_file, format_report
from caml.prepare import PrepareError


def _messy(n=400, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "customerID": [f"C{i:05d}" for i in range(n)],
        "Full Name": [f"Person Number{i}" for i in range(n)],
        "contact": [f"p{i}@example.com" for i in range(n)],     # caught by its values, not its name
        "account_id": rng.integers(0, 80, n),
        "signup_date": pd.date_range("2020-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "tenure": rng.integers(1, 72, n),
        "monthly": rng.normal(60, 20, n).round(2),
        "plan": rng.choice(["basic", "plus", "pro"], n),
        "const": 1,
        "notes": [f"customer wrote a fairly long comment number {i} about service quality" for i in range(n)],
    })
    df["Churn"] = np.where(rng.random(n) < 0.25, "Yes", "No")
    df["cancel_date"] = np.where(df["Churn"] == "Yes", "2024-05-01", None)
    df["refund_flag"] = (df["Churn"] == "Yes").astype(int)
    return df


def _cols(report: dict) -> dict[str, dict]:
    return {c["name"]: c for c in report["column_list"]}


def test_column_kinds():
    assert column_kind(pd.Series([None, None])) == "empty"
    assert column_kind(pd.Series([3, 3, 3])) == "constant"
    assert column_kind(pd.Series(["x", None, "x"])) == "one-value"
    assert column_kind(pd.Series([True, False])) == "boolean"
    assert column_kind(pd.Series([1, 2, 5])) == "integer"
    assert column_kind(pd.Series([1.5, 2.0])) == "numeric"
    assert column_kind(pd.Series(["2021-01-02", "2021-02-03 10:00"])) == "datetime"
    assert column_kind(pd.Series(["03/04/2021", "12.11.2020"])) == "datetime"
    assert column_kind(pd.Series(["a", "b", "a"])) == "categorical"


def test_flags_without_a_target():
    r = describe(_messy())
    cols = _cols(r)
    assert "id-like" in cols["customerID"]["flags"]
    assert {"id-like", "pii?"} <= set(cols["Full Name"]["flags"])
    assert "pii?" in cols["contact"]["flags"]
    assert "email addresses" in " ".join(cols["contact"]["notes"])
    assert "group-id?" in cols["account_id"]["flags"]
    assert "date" in cols["signup_date"]["flags"]
    assert "free-text" in cols["notes"]["flags"]
    assert cols["const"]["flags"] == ["constant"]
    assert cols["tenure"]["flags"] == [] and cols["monthly"]["flags"] == []
    assert r["names_needing_numbers"] == [2]
    assert [c["name"] for c in r["target_candidates"]][0] == "Churn"
    assert r["target_candidates"][0]["task_type"] == "binary"
    assert set(r["suggest_drop"]) == {"customerID", "Full Name", "contact", "const"}
    assert any("account_id" in q for q in r["ask_user"])
    assert any("signup_date" in q for q in r["ask_user"])


def test_target_report_flags_leaks_and_shows_only_target_labels():
    r = describe(_messy(), target="Churn")
    cols = _cols(r)
    assert "leak?" in cols["refund_flag"]["flags"]
    assert "leak?" in cols["cancel_date"]["flags"]   # filled in exactly for the churned rows
    assert "leak?" not in cols["tenure"]["flags"]
    t = r["target"]
    assert t["task_type_guess"] == "binary" and set(t["classes"]) == {"Yes", "No"}
    assert t["metrics_default"][0] == "auc"


def test_the_text_report_carries_no_cell_values():
    df = _messy()
    text = format_report({"file": "x.csv", **describe(df.copy(), target="Churn")})
    for col in ("customerID", "Full Name", "contact", "signup_date", "plan", "notes", "cancel_date"):
        for value in df[col].dropna().astype(str).unique()[:50]:
            assert value not in text, f"{col} value {value!r} leaked into the report"
    assert "classes: No " in text and "Yes " in text     # the target's labels are the exception
    assert "suggest_drop: --drop customerID --drop 2 --drop contact --drop const" in text
    assert "next: confirm the task with the user" in text


def test_target_by_number_and_regression_leak():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=200), "z": rng.normal(size=200)})
    df["price"] = df["x"] * 3 + rng.normal(size=200)
    df["price_eur"] = df["price"] * 0.92
    r = describe(df, target="3")
    assert r["target"]["name"] == "price" and r["target"]["task_type_guess"] == "regression"
    assert "leak?" in _cols(r)["price_eur"]["flags"]
    assert "leak?" not in _cols(r)["z"]["flags"]
    with pytest.raises(PrepareError, match="not found"):
        describe(df, target="prise")


def test_imbalance_advice_and_duplicates():
    df = pd.DataFrame({"a": list(range(196)) + [1, 1, 1, 1], "y": ["no"] * 196 + ["yes"] * 4})
    df.loc[198:, "a"] = 5
    r = describe(df, target="y")
    assert "balacc" in r["target"]["metric_advice"]
    assert r["duplicate_rows"] >= 1 and any("duplicate" in q for q in r["ask_user"])


def test_describe_file_reads_semicolons_and_cli_json(tmp_path):
    from caml.cli import main

    src = tmp_path / "d.csv"
    src.write_text("a;b;y\n" + "".join(f"{i};{i % 3},5;{'x' if i % 2 else 'z'}\n" for i in range(30)))
    r = describe_file(src)
    assert r["columns"] == 3 and "semicolon" in r["read_as"]
    out = CliRunner().invoke(main, ["describe-data", str(src), "--target", "y", "--json"])
    assert out.exit_code == 0, out.output
    assert json.loads(out.output)["target"]["task_type_guess"] == "binary"


def test_anonymize_drops_and_pseudonymizes(tmp_path):
    src = tmp_path / "people.csv"
    df = pd.DataFrame({"name": ["ann", "bob", "ann", None], "cust": [7, 8, 7, 9], "x": [1, 2, 3, 4],
                       "y": ["a", "b", "a", "b"]})
    df.to_csv(src, index=False)
    facts = anonymize_file(src, drop=["name"], hash_columns=["cust"])
    out = pd.read_csv(facts["wrote"])
    assert list(out.columns) == ["cust", "x", "y"]
    assert out["cust"][0] == out["cust"][2] != out["cust"][1]       # equal stays equal
    assert all(str(v).startswith("h_") for v in out["cust"])
    assert set(out["cust"].astype(str)).isdisjoint({"7", "8", "9"})
    assert facts["dropped"] == "name" and "can't be reversed" in facts["pseudonyms"]
    # A second run uses a fresh key: the pseudonyms can't be matched across files.
    again = pd.read_csv(anonymize_file(src, hash_columns=["2"], out=tmp_path / "b.csv")["wrote"])
    assert again["cust"][0] != out["cust"][0]
    assert (tmp_path / "people-anon.csv").stat().st_mode & 0o077 == 0


def test_anonymize_keeps_missing_values_and_can_delete_the_original(tmp_path):
    src = tmp_path / "d.csv"
    pd.DataFrame({"id": ["a", None, "b"], "v": [1, 2, 3]}).to_csv(src, index=False)
    (tmp_path / "d.csv.orig").write_text("the pre-conversion copy camlctl dataset keeps")
    facts = anonymize_file(src, hash_columns=["id"], delete_original=True)
    assert pd.read_csv(facts["wrote"])["id"].isna().tolist() == [False, True, False]
    assert not src.exists() and not (tmp_path / "d.csv.orig").exists()
    assert str(src) in facts["deleted"]


def test_anonymize_refuses_unsafe_requests(tmp_path):
    src = tmp_path / "d.csv"
    pd.DataFrame({"id": ["a", "b"], "v": [1, 2]}).to_csv(src, index=False)
    with pytest.raises(PrepareError, match="at least one column"):
        anonymize_file(src)
    with pytest.raises(PrepareError, match="both dropped and hashed"):
        anonymize_file(src, drop=["id"], hash_columns=["id"])
    with pytest.raises(PrepareError, match="every column"):
        anonymize_file(src, drop=["id", "v"])
    anonymize_file(src, drop=["id"])
    with pytest.raises(PrepareError, match="already exists"):
        anonymize_file(src, drop=["id"])


def test_cli_anonymize(tmp_path):
    from caml.cli import main

    src = tmp_path / "d.csv"
    pd.DataFrame({"Full Name": ["a", "b"], "v": [1, 2]}).to_csv(src, index=False)
    out = CliRunner().invoke(main, ["anonymize-data", str(src), "--drop", "1"])
    assert out.exit_code == 0, out.output
    assert "dropped: Full Name" in out.output and "next: caml describe-data" in out.output
