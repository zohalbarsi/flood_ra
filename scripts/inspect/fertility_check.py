"""Births in infoUSA vs the ACS, NC and SC, by year.

infoUSA has no birth records: new children are the rise in a household's children
count (CHILDRENHHCOUNT) from one year's file to the next. Households: primary families
in NC or SC in year t that were also in the household panel in t-1 (step 08), with a
known count in both years. Women 15-50: listed in those households in t (sex and age
of the adult slots). Fertility rate: new children per 1,000 women 15-50. ACS rate:
women 15-50 with a birth in the past 12 months per 1,000 women 15-50 (B13002).

Run on the server after step 08:
    python scripts/inspect/fertility_check.py
Writes output/logs/fertility_check.md and output/tables/fertility_by_year.csv; the ACS
table is cached in benchmarks/acs1_state_births.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import census, db, geo, panel, paths, settings  # noqa: E402
from flood_ra.report import table  # noqa: E402

REPORT = paths.LOG_DIR / "fertility_check.md"
TABLE = paths.REPO_ROOT / "output" / "tables" / "fertility_by_year.csv"
BIRTHS = {"B13002_001E": "women_15_50", "B13002_002E": "women_with_birth"}
MODEL_CHANGES = {2012, 2016}  # Data Axle's children model steps up (README, data breaks)


def panel_file(year: int) -> Path:
    return panel.DIR / f"panel_{year}.parquet"


def text(c: str) -> str:
    return f"upper(trim(CAST({c} AS VARCHAR)))"


def infousa(con, years: list[int], files: dict[int, Path]) -> tuple[pd.DataFrame, dict]:
    """Per state and year: households, women 15-50 in them, new children; and a check of the sex codes."""
    count = "coalesce({k}.n_kids, CASE WHEN {k}.kids = 0 THEN 0 END)"  # no children: count 0
    cur, prev = count.format(k="c"), count.format(k="p")
    rows, check = [], {"adults": 0, "female": 0, "female_with_age": 0}
    for t in years:
        conv = f"read_parquet('{files[t].as_posix()}')"
        cols = {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {conv}").fetchall()}
        slots = [i for i in range(1, 6) if f"Gender_{i}" in cols and f"Age_{i}" in cols]
        age = lambda i: f"TRY_CAST({text(f'Age_{i}')} AS INTEGER)"  # noqa: E731
        women = " + ".join(f"coalesce(({text(f'Gender_{i}')} = 'F' AND {age(i)} BETWEEN 15 AND 50)::INT, 0)"
                           for i in slots) or "NULL::INT"
        rows.append(con.sql(f"""
            WITH w AS (SELECT trim(FAMILYID) AS fid, max({women}) AS women FROM {conv}
                       WHERE {text('PRIMARY_FAMILY_IND')} = '1' GROUP BY 1)
            SELECT c.state, count(*) AS households, sum(w.women) AS women_15_50,
                   sum(greatest({cur} - {prev}, 0)) AS new_children
            FROM read_parquet('{panel_file(t).as_posix()}') c
            JOIN read_parquet('{panel_file(t - 1).as_posix()}') p USING (hhid)
            LEFT JOIN w ON w.fid = c.fid
            WHERE c.in_study AND c.prim AND {cur} IS NOT NULL AND {prev} IS NOT NULL
            GROUP BY c.state""").df().assign(year=t))
        if slots:
            pairs = ", ".join(f"{{'sex': {text(f'Gender_{i}')}, 'age': {age(i)}}}" for i in slots)
            a, f, fa = con.sql(f"""SELECT count(*) FILTER (WHERE p.sex <> ''), count(*) FILTER (WHERE p.sex = 'F'),
                                          count(*) FILTER (WHERE p.sex = 'F' AND p.age IS NOT NULL)
                                   FROM (SELECT unnest([{pairs}]) AS p FROM {conv})""").fetchall()[0]
            check = {"adults": check["adults"] + a, "female": check["female"] + f,
                     "female_with_age": check["female_with_age"] + fa}
    return pd.concat(rows, ignore_index=True), check


def main() -> None:
    files = paths.chosen_files()
    start, last = (settings.FIRST_YEAR or 2011) + 1, settings.LAST_YEAR or 2024
    years = [t for t in range(start, last + 1)
             if t in files and panel_file(t).exists() and panel_file(t - 1).exists()]
    if not years:
        sys.exit(f"no consecutive panel files in {panel.DIR}; run step 08 first")
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    iu, check = infousa(con, years, files)
    states = geo.study_states()
    acs, notes = census.state_series(years, [geo.STATE_FIPS[s] for s in states], BIRTHS, "acs1_state_births.csv")
    acs_rate = pd.DataFrame({"year": [], "state": [], "acs_rate": []})
    if len(acs) and set(BIRTHS.values()) <= set(acs.columns):
        acs_rate = pd.DataFrame({"year": acs["year"].astype("int64"),
                                 "state": acs["state"].map({v: k for k, v in geo.STATE_FIPS.items()}),
                                 "acs_rate": 1000 * acs["women_with_birth"] / acs["women_15_50"]})
    d = iu.merge(acs_rate.astype({"year": "int64"}), on=["year", "state"], how="left")
    d["fertility_rate"] = 1000 * d["new_children"] / d["women_15_50"].where(d["women_15_50"] > 0)
    order = {s: i for i, s in enumerate(states)}
    d = d.sort_values(["year", "state"], key=lambda c: c.map(order) if c.name == "state" else c)
    d = d[["year", "state", "households", "women_15_50", "new_children", "fertility_rate", "acs_rate"]]
    d.round(1).to_csv(TABLE, index=False)

    num = lambda s: s.map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")  # noqa: E731
    one = lambda s: s.map(lambda v: "" if pd.isna(v) else f"{v:.1f}")  # noqa: E731
    show = pd.DataFrame({
        "year": d["year"].astype(str) + d["year"].isin(MODEL_CHANGES).map({True: "*", False: ""}),
        "state": d["state"], "households": num(d["households"]), "women 15-50": num(d["women_15_50"]),
        "new children": num(d["new_children"]), "fertility rate": one(d["fertility_rate"]),
        "ACS rate": one(d["acs_rate"])})
    share = lambda a, b: f"{a / b:.0%}" if b else "n/a"  # noqa: E731
    REPORT.write_text("\n".join([
        "# Births: infoUSA vs ACS, NC and SC", "",
        "infoUSA has no birth records: new children are the rise in a household's children count "
        "(CHILDRENHHCOUNT) from one year to the next. Households: primary families in the state that year that "
        "were also in the household panel the year before (step 08), with a known count in both years. Women "
        "15-50: listed in those households (sex and age of the adult slots). Fertility rate: new children per "
        "1,000 women 15-50. ACS rate: women 15-50 with a birth in the past 12 months per 1,000 women 15-50 "
        "(B13002, 1-year estimates; no 2020 release).", "",
        *table(show),
        "\\* Data Axle changed its children model in 2012 and 2016: new children in those years are mostly "
        "recoding, not births.", "",
        f"Check: listed adults coded F: {share(check['female'], check['adults'])}; of them, with an age: "
        f"{share(check['female_with_age'], check['female'])}.", "",
        *(["Notes: " + "; ".join(notes), ""] if notes else []),
        census.cache_note(), "",
    ]))
    print(f"wrote {REPORT} and {TABLE}")


if __name__ == "__main__":
    main()
