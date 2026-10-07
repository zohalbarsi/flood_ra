"""Helpers for the markdown logs. Logs hold counts and shares only, never
record values, so they are safe to commit."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def pct(x) -> str:
    return "" if x is None or pd.isna(x) else f"{100 * x:.1f}%"


def table(df: pd.DataFrame) -> list[str]:
    return ["```", df.to_string(index=False), "```", ""]


def mask(v) -> str:
    """A code value as shown in a report: codes of up to 4 characters as they
    are, longer values as their pattern (9 = digit, A = letter)."""
    if v is None or pd.isna(v):
        return "(missing)"
    if v == "":
        return "(empty)"
    return v if len(v) <= 4 else re.sub("[A-Za-z]", "A", re.sub(r"\d", "9", v))


def code_shares(con, files: dict[int, Path], col: str, top: int = 6) -> pd.DataFrame:
    """Share of households per value of a code column, one row per year;
    values beyond the `top` most common overall are pooled as "other"."""
    rows = []
    for year, f in files.items():
        rows += [(year, mask(v), n) for v, n in con.sql(
            f"SELECT trim(\"{col}\"), count(*) FROM read_parquet('{f.as_posix()}') GROUP BY 1").fetchall()]
    df = pd.DataFrame(rows, columns=["year", "value", "n"]).groupby(["year", "value"], as_index=False)["n"].sum()
    keep = df.groupby("value")["n"].sum().nlargest(top).index
    df.loc[~df["value"].isin(keep), "value"] = "other"
    df = df.pivot_table(index="year", columns="value", values="n", aggfunc="sum", fill_value=0)
    df.columns.name = None
    return df.div(df.sum(axis=1), axis=0).map(pct).reset_index()
