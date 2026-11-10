"""Births in infoUSA vs the ACS, NC and SC, by year.

infoUSA has no birth records: a birth can only show up as a household's children
count (CHILDRENHHCOUNT) going up from one year's file to the next. For each year t,
among primary-family households in NC or SC in t that were also in the household
panel in t-1 (step 08, so households that continue under a new FAMILYID count),
it sums the increases ("children added"). ACS benchmark: women 15-50 with a birth
in the past 12 months (B13002), 1-year state estimates; both per 1,000 households
(ACS: B25003).

Run on the server after step 08:
    python scripts/inspect/fertility_check.py
Writes output/logs/fertility_check.md and output/tables/fertility_by_year.csv
(counts and rates only); the ACS table is cached in benchmarks/acs1_state_births.csv.
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


def infousa(con, years: list[int]) -> pd.DataFrame:
    """Year-to-year changes in the children count, by state of the year-t record."""
    count = "coalesce({k}.n_kids, CASE WHEN {k}.kids = 0 THEN 0 END)"  # no children: count 0
    cur, prev = count.format(k="c"), count.format(k="p")
    known = f"{cur} IS NOT NULL AND {prev} IS NOT NULL"
    rows = []
    for t in years:
        rows.append(con.sql(f"""
            SELECT c.state, count(*) AS households, count(*) FILTER (WHERE {known}) AS count_known,
                   count(*) FILTER (WHERE {cur} > {prev}) AS households_more_children,
                   coalesce(sum(greatest({cur} - {prev}, 0)), 0) AS children_added,
                   coalesce(sum(greatest({prev} - {cur}, 0)), 0) AS children_removed,
                   count(*) FILTER (WHERE c.kids IN (0, 1) AND p.kids IN (0, 1)) AS flag_known,
                   count(*) FILTER (WHERE c.kids = 1 AND p.kids = 0) AS flag_turned_on,
                   count(*) FILTER (WHERE c.moved = false AND {known}) AS same_address_known,
                   coalesce(sum(greatest({cur} - {prev}, 0)) FILTER (WHERE c.moved = false), 0)
                       AS same_address_children_added
            FROM read_parquet('{panel_file(t).as_posix()}') c
            JOIN read_parquet('{panel_file(t - 1).as_posix()}') p USING (hhid)
            WHERE c.in_study AND c.prim
            GROUP BY c.state""").df().assign(year=t))
    return pd.concat(rows, ignore_index=True)


def acs(years: list[int], fips: list[str]) -> tuple[pd.DataFrame, list[str]]:
    births, notes = census.state_series(years, fips, BIRTHS, "acs1_state_births.csv")
    hh, more = census.state_series(years, fips)
    cols = ["year", "state"]
    a = hh[cols + ["households"]] if len(hh) else pd.DataFrame({"year": [], "state": [], "households": []})
    if len(births):
        a = a.merge(births[cols + [c for c in BIRTHS.values() if c in births]], on=cols, how="outer")
    for c in BIRTHS.values():
        if c not in a:
            a[c] = float("nan")
    a = a.astype({"year": "int64"})
    a["state"] = a["state"].map({v: k for k, v in geo.STATE_FIPS.items()})
    return a[a["year"].isin(years)].rename(columns={"households": "acs_households"}), notes + more


def main() -> None:
    start, last = (settings.FIRST_YEAR or 2011) + 1, settings.LAST_YEAR or 2024
    years = [t for t in range(start, last + 1) if panel_file(t).exists() and panel_file(t - 1).exists()]
    if not years:
        sys.exit(f"no consecutive panel files in {panel.DIR}; run step 08 first")
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    iu = infousa(con, years)
    states = geo.study_states()
    a, notes = acs(years, [geo.STATE_FIPS[s] for s in states])
    d = iu.merge(a, on=["year", "state"], how="left")
    total = (d.groupby("year", as_index=False).sum(numeric_only=True, min_count=len(states))
             .assign(state="+".join(states)))
    order = {st: i for i, st in enumerate([*states, "+".join(states)])}
    d = pd.concat([d, total], ignore_index=True)
    d = d.sort_values(["state", "year"], key=lambda c: c.map(order) if c.name == "state" else c).reset_index(drop=True)
    per = lambda a, b: 1000 * d[a] / d[b].where(d[b] > 0)  # noqa: E731
    d["children_added_per_1000"] = per("children_added", "count_known")
    d["more_children_per_1000"] = per("households_more_children", "count_known")
    d["flag_on_per_1000"] = per("flag_turned_on", "flag_known")
    d["same_address_added_per_1000"] = per("same_address_children_added", "same_address_known")
    d["children_removed_per_1000"] = per("children_removed", "count_known")
    d["acs_births_per_1000_households"] = per("women_with_birth", "acs_households")
    d["acs_births_per_1000_women"] = per("women_with_birth", "women_15_50")
    d["ratio"] = d["children_added_per_1000"] / d["acs_births_per_1000_households"]
    d["model_change"] = d["year"].isin(MODEL_CHANGES)
    d.round(4).to_csv(TABLE, index=False)

    num = lambda s: s.map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")  # noqa: E731
    one = lambda s: s.map(lambda v: "" if pd.isna(v) else f"{v:.1f}")  # noqa: E731
    year = d["year"].astype(str) + d["model_change"].map({True: "*", False: ""})
    main_table = pd.DataFrame({
        "year": year, "state": d["state"], "households, both years": num(d["count_known"]),
        "children added": num(d["children_added"]), "per 1,000": one(d["children_added_per_1000"]),
        "ACS births": num(d["women_with_birth"]), "ACS per 1,000": one(d["acs_births_per_1000_households"]),
        "infoUSA / ACS": d["ratio"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")})
    detail = pd.DataFrame({
        "year": year, "state": d["state"], "more children": one(d["more_children_per_1000"]),
        "flag turned on": one(d["flag_on_per_1000"]), "added, same address": one(d["same_address_added_per_1000"]),
        "removed": one(d["children_removed_per_1000"]),
        "ACS births per 1,000 women 15-50": one(d["acs_births_per_1000_women"])})
    ok = d[(d["state"] == "+".join(states)) & ~d["model_change"] & d["ratio"].notna()]
    rate_iu = ok["children_added"].sum() / ok["count_known"].sum() * 1000 if len(ok) else None
    rate_acs = ok["women_with_birth"].sum() / ok["acs_households"].sum() * 1000 if len(ok) else None
    summary = (f"Years with both measures, outside the {' and '.join(map(str, sorted(MODEL_CHANGES)))} model changes "
               f"({', '.join(map(str, ok['year']))}), {'+'.join(states)}: infoUSA adds {rate_iu:.1f} children per "
               f"1,000 households a year, the ACS records {rate_acs:.1f} births per 1,000 households "
               f"(infoUSA / ACS = {rate_iu / rate_acs:.2f}).") if len(ok) else "No year has both measures yet."
    REPORT.write_text("\n".join([
        "# Births: infoUSA vs ACS, NC and SC (counts and rates only)", "",
        "infoUSA has no birth records. A birth can only show up as a household's children count "
        "(CHILDRENHHCOUNT; 0 when CHILDREN_IND says no children) rising from one year's file to the next. "
        "**infoUSA:** primary-family households in the state in year t that were also in the household panel in "
        "t-1 (step 08, so households continuing under a new FAMILYID count), with a known count in both years; "
        "children added = sum of the increases. **ACS:** women 15-50 with a birth in the past 12 months "
        "(B13002, 1-year estimates; twins count once), per 1,000 households (B25003). The ACS 1-year 2020 "
        "release does not exist.", "",
        summary, "",
        "## Children added (infoUSA) vs births (ACS)", "",
        *table(main_table),
        "\\* Data Axle changed its children model: the share of households with children steps up (10% to 20% "
        "in 2012, to 30% in 2016), so most of the increase in these years is recoding, not births.", "",
        "## Detail (per 1,000 households)", "",
        "More children: households whose count rose. Flag turned on: households whose CHILDREN_IND went from 0 "
        "to 1. Added, same address: children added among households at the same address both years "
        "(moves can rebuild a record). Removed: the sum of decreases (children aging out or leaving, or "
        "recoding). Last column: an ACS check (about 50-60 is normal).", "",
        *table(detail),
        "## Reading the comparison", "",
        "- The count also rises when children move in (new partners, relatives) and when Data Axle's "
        "model updates a household; a birth in the same year a child leaves the household is missed.",
        "- Timing differs: the ACS counts births in the 12 months before the interview (spread over year t); "
        "infoUSA, changes between the t-1 and t files.",
        "- Households seen only in t (new households, including new parents who set up a home) are not "
        "counted.", "",
        *(["Notes: " + "; ".join(notes), ""] if notes else []),
        census.cache_note(), "",
    ]))
    print(f"wrote {REPORT} and {TABLE}")


if __name__ == "__main__":
    main()
