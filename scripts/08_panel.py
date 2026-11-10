from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, ethnicity, geo, panel, paths, settings  # noqa: E402
from flood_ra.address import address_key  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

BASE_YEAR = 2017      # last year before Florence: defines the cohort and the exposure
MIN_CELL = 10         # destination states with fewer households are pooled
GEO = "als2010"       # 2010 Census codes, filled in every state
REPORT = paths.LOG_DIR / "panel_report.md"
TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURES = paths.REPO_ROOT / "output" / "figures"
FAM = f"(SELECT id FROM read_parquet('{panel.IDS_FAMILY.as_posix()}'))"  # narrowed in main to the panel years
PER = f"(SELECT id FROM read_parquet('{panel.IDS_PERSON.as_posix()}'))"


def rows_file(year: int, k: int | str = "*") -> str:
    """Work file(s) with one row per FAMILYID; slice k, or all slices for "*"."""
    return (panel.WORK / f"rows_{year}_{k}.parquet").as_posix()


def persons_file(year: int, k: int | str = "*") -> str:
    return (panel.WORK / f"persons_{year}_{k}.parquet").as_posix()


def final_file(year: int) -> Path:
    return panel.DIR / f"panel_{year}.parquet"


def in_slice(col: str, k: int) -> str:
    return f"hash({col}) % {panel.SLICES} = {k}"


def columns(con, src: str) -> set[str]:
    return {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {src}").fetchall()}


def standard_sql(src: str, cols: set[str], source: str, states: list[str]) -> str:
    """One row per record with the panel's fields, from a converted or a national file."""
    def v(name: str) -> str:  # a column as trimmed text, NULL if the file lacks it
        return f'trim(CAST("{name}" AS VARCHAR))' if name in cols else "NULL::VARCHAR"

    def num(name: str) -> str:
        return f"TRY_CAST({v(name)} AS INTEGER)"

    return f"""
        SELECT year, trim(FAMILYID) AS fid,
               coalesce({v('PRIMARY_FAMILY_IND')} = '1', false) AS prim,
               upper(trim(STATE)) AS state,
               coalesce(upper(trim(STATE)) IN ({', '.join(repr(s) for s in states)}), false) AS in_study,
               {geo.county_fips(GEO)} AS county, {geo.tract_geoid(GEO)} AS tract,
               {address_key(cols, True, compact=True)} AS addr,
               {num('OWNER_RENTER_STATUS')} AS owner_code, {num('FIND_DIV_1000')} * 1000 AS income,
               {num('WEALTH_FINDER_SCORE')} AS wealth, {num('ESTMTD_HOME_VAL_DIV_1000')} * 1000 AS home_value,
               {num('CHILDREN_IND')} AS kids, {num('CHILDRENHHCOUNT')} AS n_kids,
               nullif(upper({v('HEAD_HH_AGE_CODE')}), '') AS head_age, {num('MARITAL_STATUS')} AS marital,
               {num('LENGTH_OF_RESIDENCE')} AS lor, {num('RECENCY_DATE')} AS recency,
               nullif(upper({v('Ethnicity_Code_1')}), '') AS eth_code,
               len(list_filter({panel.persons_list(cols)}, x -> x IS NOT NULL)) AS n_adults,
               {panel.persons_list(cols)} AS persons, '{source}' AS source
        FROM {src}"""


def year_rows(con, year: int, conv: Path, states: list[str]) -> tuple[int, int]:
    """Work files for one year, in slices of FAMILYIDs: one row per FAMILYID
    (panel households, and other households holding a panel adult, which may
    continue one) and the FAMILYID's adults."""
    src = f"read_parquet('{conv.as_posix()}')"
    cols = columns(con, src)
    # other households' adults, then those that are panel adults (one ID list in memory at a time)
    con.sql(f"""CREATE OR REPLACE TEMP TABLE other_adults AS
        SELECT trim(FAMILYID) AS fid, unnest({panel.persons_list(cols)}) AS p FROM {src}
        WHERE trim(FAMILYID) NOT IN {FAM}""")
    con.sql(f"CREATE OR REPLACE TEMP TABLE extra AS SELECT DISTINCT fid FROM other_adults WHERE p IN {PER}")
    con.sql("DROP TABLE other_adults")
    conv_rows = (panel.WORK / f"study_{year}.parquet").as_posix()
    con.sql(f"""COPY (SELECT * FROM ({standard_sql(src, cols, 'study states', states)})
                      WHERE fid IN {FAM} OR fid IN (SELECT fid FROM extra))
                TO '{conv_rows}' (FORMAT parquet, COMPRESSION zstd)""")
    con.sql("DROP TABLE extra")
    nat_src = f"read_parquet('{panel.national_file(year).as_posix()}')"
    nat = standard_sql(nat_src, columns(con, nat_src), "other states", states)
    for k in range(panel.SLICES):
        con.sql(f"""CREATE OR REPLACE TEMP TABLE recs AS
            SELECT * FROM (SELECT * FROM read_parquet('{conv_rows}') UNION ALL BY NAME {nat})
            WHERE fid IS NOT NULL AND {in_slice('fid', k)}""")
        # national records matched through two adults appear twice: rows keep one record per FAMILYID
        con.sql(f"""COPY (
            WITH a AS (SELECT fid, count(DISTINCT addr) AS n_addresses,
                              min(state) IS DISTINCT FROM max(state) AS multi_state
                       FROM recs GROUP BY fid)
            SELECT r.* EXCLUDE (persons), a.n_addresses, a.multi_state
            FROM recs r JOIN a USING (fid)
            QUALIFY row_number() OVER (PARTITION BY r.fid ORDER BY r.prim DESC, r.recency DESC NULLS LAST,
                                       r.in_study DESC, r.addr NULLS LAST) = 1
        ) TO '{rows_file(year, k)}' (FORMAT parquet, COMPRESSION zstd)""")
        con.sql(f"""COPY (SELECT DISTINCT fid, p AS person FROM (SELECT fid, unnest(persons) AS p FROM recs)
                          WHERE p IS NOT NULL)
                    TO '{persons_file(year, k)}' (FORMAT parquet, COMPRESSION zstd)""")
    con.sql("DROP TABLE recs")
    Path(conv_rows).unlink()
    return con.sql(f"SELECT count(*), count(*) FILTER (WHERE source = 'other states') "
                   f"FROM read_parquet('{rows_file(year)}')").fetchall()[0]


def link_pair(con, t: int, t1: int) -> None:
    """Households in year t whose FAMILYID is not in year t1: where their adults
    are in t1. A FAMILYID continues the household if it is new in t1 (not in
    table seen, the FAMILYIDs of earlier years), holds all the adults found and
    no one else, and no other household points to it. Adds continuing FAMILYIDs
    to table succ (with the household's hhid) and every case to table links."""
    con.sql(f"""CREATE OR REPLACE TEMP TABLE gone AS
        SELECT fid FROM read_parquet('{rows_file(t)}')
        WHERE fid NOT IN (SELECT fid FROM read_parquet('{rows_file(t1)}'))
          AND (fid IN {FAM} OR fid IN (SELECT fid FROM succ))""")
    con.sql(f"""CREATE OR REPLACE TEMP TABLE gp AS
        SELECT DISTINCT fid, person FROM read_parquet('{persons_file(t)}') WHERE fid IN (SELECT fid FROM gone)""")
    con.sql(f"""CREATE OR REPLACE TEMP TABLE cand AS
        SELECT DISTINCT gp.fid, q.fid AS successor
        FROM gp JOIN read_parquet('{persons_file(t1)}') q ON q.person = gp.person
        WHERE q.fid != gp.fid""")
    con.sql(f"""CREATE OR REPLACE TEMP TABLE kinds AS
        WITH n AS (SELECT fid, count(*) AS k, any_value(successor) AS successor FROM cand GROUP BY fid),
             shared AS (SELECT successor FROM cand GROUP BY successor HAVING count(*) > 1),
             -- successors that also hold an adult who was not in the household
             outsiders AS (SELECT DISTINCT n.fid FROM n
                           JOIN read_parquet('{persons_file(t1)}') q ON q.fid = n.successor
                           LEFT JOIN gp ON gp.fid = n.fid AND gp.person = q.person
                           WHERE n.k = 1 AND gp.person IS NULL)
        SELECT g.fid, n.successor,
               CASE WHEN n.fid IS NULL THEN 'not found'
                    WHEN n.k > 1 THEN 'split'
                    WHEN n.successor NOT IN (SELECT fid FROM seen)
                         AND n.successor NOT IN (SELECT successor FROM shared)
                         AND g.fid NOT IN (SELECT fid FROM outsiders) THEN 'continues'
                    ELSE 'joined' END AS kind
        FROM gone g LEFT JOIN n USING (fid)""")
    con.sql(f"""INSERT INTO succ
        SELECT k.successor, coalesce(s.hhid, k.fid), {t1}
        FROM kinds k LEFT JOIN succ s ON s.fid = k.fid WHERE k.kind = 'continues'""")
    con.sql(f"INSERT INTO links SELECT {t1}, fid, CASE WHEN kind = 'continues' THEN successor END, kind "
            "FROM kinds")
    for name in ("gone", "gp", "cand", "kinds"):
        con.sql(f"DROP TABLE {name}")


def final_year(con, t: int, prev: int | None) -> None:
    """The panel rows of year t: one per household (hhid), with the change since
    the household's row in the previous file year. Built in slices of hhid."""
    parts = []
    for k in range(panel.SLICES):
        con.sql(f"""CREATE OR REPLACE TEMP TABLE cur AS
            SELECT coalesce(s.hhid, r.fid) AS hhid, s.hhid IS NOT NULL AS linked, r.*,
                   CASE WHEN r.owner_code BETWEEN 7 AND 9 THEN 'owner'
                        WHEN r.owner_code BETWEEN 0 AND 3 THEN 'renter' ELSE 'unknown' END AS tenure
            FROM read_parquet('{rows_file(t)}') r LEFT JOIN succ s ON s.fid = r.fid
            WHERE (r.fid IN {FAM} OR s.fid IS NOT NULL) AND {in_slice('coalesce(s.hhid, r.fid)', k)}
            QUALIFY row_number() OVER (PARTITION BY coalesce(s.hhid, r.fid)
                                       ORDER BY r.prim DESC, r.recency DESC NULLS LAST, r.in_study DESC,
                                                r.fid) = 1""")
        p = (f"(SELECT hhid, addr, state, in_study, tenure FROM read_parquet('{final_file(prev).as_posix()}') "
             f"WHERE {in_slice('hhid', k)})" if prev is not None
             else "(SELECT hhid, addr, state, in_study, tenure FROM cur WHERE false)")
        part = (panel.WORK / f"final_{t}_{k}.parquet").as_posix()
        con.sql(f"""COPY (
            SELECT c.*,
                   {ethnicity.sql_category('c.eth_code')} AS eth_category,
                   {ethnicity.sql_broad('c.eth_code')} AS eth_broad,
                   p.hhid IS NOT NULL AS seen_before,
                   CASE WHEN p.hhid IS NOT NULL AND c.addr IS NOT NULL AND p.addr IS NOT NULL
                        THEN c.addr != p.addr END AS moved,
                   CASE WHEN p.hhid IS NOT NULL THEN p.in_study AND NOT c.in_study END AS left_study,
                   CASE WHEN p.hhid IS NOT NULL THEN NOT p.in_study AND c.in_study END AS entered_study,
                   p.state AS state_before, p.in_study AS in_study_before, p.tenure AS tenure_before
            FROM cur c LEFT JOIN {p} p USING (hhid)
        ) TO '{part}' (FORMAT parquet, COMPRESSION zstd)""")
        parts.append(part)
    src = "read_parquet([" + ", ".join(f"'{x}'" for x in parts) + "])"
    # wealth rank within the year (percent rank: share of households with lower wealth)
    con.sql(f"""CREATE OR REPLACE TEMP TABLE wr AS
        SELECT wealth, coalesce(sum(n) OVER (ORDER BY wealth ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                       / nullif(sum(n) OVER () - 1, 0) AS wealth_rank
        FROM (SELECT wealth, count(*) AS n FROM {src} WHERE wealth IS NOT NULL GROUP BY wealth)""")
    tmp = final_file(t).with_suffix(".parquet.tmp")
    con.sql(f"COPY (SELECT f.*, wr.wealth_rank FROM {src} f LEFT JOIN wr USING (wealth)) "
            f"TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    tmp.replace(final_file(t))
    for x in parts:
        Path(x).unlink()
    con.sql("DROP TABLE cur")
    con.sql("DROP TABLE wr")


def panel_ids(con, files: dict[int, Path], years: list[int], states: list[str]) -> str:
    """FAMILYIDs that are a primary family in a study state in at least one
    panel year (step 07's list covers every analysis year), in slices."""
    out = panel.WORK / "family"
    out.mkdir(parents=True, exist_ok=True)
    src = "read_parquet([" + ", ".join(f"'{files[y].as_posix()}'" for y in years) + "], union_by_name=true)"
    for k in range(panel.SLICES):
        con.sql(f"""COPY (SELECT DISTINCT trim(FAMILYID) AS id FROM {src}
                          WHERE upper(trim(STATE)) IN ({', '.join(repr(s) for s in states)})
                            AND trim(PRIMARY_FAMILY_IND) = '1' AND nullif(trim(FAMILYID), '') IS NOT NULL
                            AND {in_slice('trim(FAMILYID)', k)})
                    TO '{(out / f"part_{k}.parquet").as_posix()}' (FORMAT parquet)""")
    return f"(SELECT id FROM read_parquet('{(out / 'part_*.parquet').as_posix()}'))"


def drop_work(year: int) -> None:
    """Remove a year's work files once the next year is linked."""
    for x in [*panel.WORK.glob(f"rows_{year}_*.parquet"), *panel.WORK.glob(f"persons_{year}_*.parquet")]:
        x.unlink()


def household_table(con, years: list[int]) -> list[str]:
    """households.parquet: one row per household, built in slices of hhid;
    returns notes for the report."""
    notes = []
    finals = "read_parquet([" + ", ".join(f"'{final_file(y).as_posix()}'" for y in years) + "])"
    merged = paths.MERGED / f"infousa_flood_{BASE_YEAR}.parquet"
    exposure = None
    if BASE_YEAR in years and merged.exists():
        mcols = columns(con, f"read_parquet('{merged.as_posix()}')")
        keep = [c for c in ("in_flood_counties", "block_exposure_ok", "tract_geoid", "bg_geoid", "block_geoid")
                if c in mcols] + sorted(c for c in mcols if re.match(r"^(tract|bg|block)_pct_flooded_", c))
        for k in range(panel.SLICES):  # one record per FAMILYID, primary family first
            con.sql(f"""COPY (
                SELECT trim(FAMILYID) AS fid, {', '.join(keep)} FROM read_parquet('{merged.as_posix()}')
                WHERE {in_slice('trim(FAMILYID)', k)}
                QUALIFY row_number() OVER (PARTITION BY trim(FAMILYID)
                                           ORDER BY coalesce(trim(PRIMARY_FAMILY_IND) = '1', false) DESC) = 1
            ) TO '{(panel.WORK / f"exposure_{k}.parquet").as_posix()}' (FORMAT parquet)""")
        exposure = f"read_parquet('{(panel.WORK / 'exposure_*.parquet').as_posix()}')"
    else:
        notes.append(f"no flood exposure: {merged.name} not found (run step 04)" if BASE_YEAR in years
                     else f"{BASE_YEAR} is not among the panel years: no base-year address or exposure")
    parts = []
    for k in range(panel.SLICES):
        base = (f"""(SELECT hhid, fid AS fid_base, true AS present_base, in_study AS in_study_base,
                            state AS state_base, county AS county_base, tract AS tract_base,
                            tenure AS tenure_base
                     FROM read_parquet('{final_file(BASE_YEAR).as_posix()}') WHERE {in_slice('hhid', k)})"""
                if BASE_YEAR in years else "(SELECT NULL::VARCHAR AS hhid WHERE false)")
        part = (panel.WORK / f"households_{k}.parquet").as_posix()
        con.sql(f"""COPY (
            WITH y AS (SELECT hhid, min(year) AS first_year, max(year) AS last_year, count(*) AS n_years,
                              count(*) FILTER (WHERE in_study) AS n_years_study, bool_or(linked) AS linked
                       FROM {finals} WHERE {in_slice('hhid', k)} GROUP BY hhid),
                 b AS {base}
            SELECT y.*, b.* EXCLUDE (hhid){', e.* EXCLUDE (fid)' if exposure else ''}
            FROM y LEFT JOIN b USING (hhid) {f'LEFT JOIN {exposure} e ON e.fid = b.fid_base' if exposure else ''}
        ) TO '{part}' (FORMAT parquet)""")
        parts.append(part)
    con.sql("COPY (SELECT * FROM read_parquet([" + ", ".join(f"'{x}'" for x in parts) + "])) "
            f"TO '{(panel.DIR / 'households.parquet').as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    for x in [*parts, *panel.WORK.glob("exposure_*.parquet")]:
        Path(x).unlink()
    return notes


def ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.where(b > 0)


def report_tables(con, years: list[int]) -> dict[str, pd.DataFrame]:
    finals = "read_parquet([" + ", ".join(f"'{final_file(y).as_posix()}'" for y in years) + "])"
    out = {}
    out["by_year"] = con.sql(f"""
        SELECT year, count(*) AS households, count(*) FILTER (WHERE in_study) AS in_study_states,
               count(*) FILTER (WHERE NOT in_study) AS other_states,
               count(*) FILTER (WHERE linked) AS under_new_familyid,
               count(*) FILTER (WHERE seen_before) AS seen_before,
               count(*) FILTER (WHERE moved) AS moved, count(moved) AS moved_known,
               count(*) FILTER (WHERE moved AND in_study AND in_study_before) AS moved_within,
               count(*) FILTER (WHERE in_study_before) AS in_study_before,
               count(*) FILTER (WHERE left_study) AS left_study,
               count(*) FILTER (WHERE NOT in_study_before) AS outside_before,
               count(*) FILTER (WHERE entered_study) AS entered_study
        FROM {finals} GROUP BY year ORDER BY year""").df()
    out["links"] = con.sql("""
        SELECT year, count(*) AS not_found_by_familyid,
               count(*) FILTER (WHERE kind = 'continues') AS continues_new_familyid,
               count(*) FILTER (WHERE kind = 'joined') AS joined_other_household,
               count(*) FILTER (WHERE kind = 'split') AS split,
               count(*) FILTER (WHERE kind = 'not found') AS adults_not_found
        FROM links GROUP BY year ORDER BY year""").df()
    dest = con.sql(f"""
        SELECT state, count(*) AS households,
               count(*) FILTER (WHERE year = {BASE_YEAR + 2}) AS households_after_florence
        FROM {finals} WHERE left_study GROUP BY state""").df()
    small = dest["households"] < MIN_CELL
    if small.any():
        pooled = pd.DataFrame([{"state": f"other ({small.sum()} states with fewer than {MIN_CELL})",
                                "households": dest.loc[small, "households"].sum(),
                                "households_after_florence": dest.loc[small, "households_after_florence"].sum()}])
        dest = pd.concat([dest[~small], pooled], ignore_index=True)
    dest["share"] = dest["households"] / dest["households"].sum() if len(dest) else []
    dest = dest.sort_values("households", ascending=False, key=lambda s: s.where(~dest["state"].str.startswith("other"), -1))
    # small counts in the post-Florence column are shown as <10
    dest["households_after_florence"] = dest["households_after_florence"].map(
        lambda n: f"<{MIN_CELL}" if 0 < n < MIN_CELL else f"{n:,}")
    out["destinations"] = dest
    measures = """count(*) FILTER (WHERE owner_code BETWEEN 7 AND 9)
                      / nullif(count(*) FILTER (WHERE owner_code BETWEEN 0 AND 9), 0) AS owner_share,
                  count(*) FILTER (WHERE kids = 1) / nullif(count(kids), 0) AS children_share,
                  median(income) AS median_income"""
    cohort = (con.sql(f"""
        WITH coh AS (SELECT hhid FROM read_parquet('{final_file(BASE_YEAR).as_posix()}') WHERE in_study)
        SELECT year, count(*) AS cohort_found, count(*) FILTER (WHERE in_study) AS cohort_in_study_states,
               {measures.replace('AS ', 'AS cohort_')}
        FROM {finals} SEMI JOIN coh USING (hhid) GROUP BY year""").df()
        if BASE_YEAR in years else pd.DataFrame({"year": years}))
    cross = con.sql(f"""SELECT year, {measures.replace('AS ', 'AS all_')}
                        FROM {finals} WHERE in_study GROUP BY year""").df()
    out["cohort"] = cross.merge(cohort, on="year", how="left").sort_values("year")
    out["tenure_changes"] = con.sql(f"""
        SELECT year, count(*) AS same_address,
               count(*) FILTER (WHERE tenure_before = 'owner' AND tenure = 'renter') AS owner_to_renter,
               count(*) FILTER (WHERE tenure_before = 'owner' AND tenure = 'unknown') AS owner_to_unknown,
               count(*) FILTER (WHERE tenure_before = 'renter' AND tenure = 'owner') AS renter_to_owner,
               count(*) FILTER (WHERE tenure_before = 'unknown' AND tenure = 'owner') AS unknown_to_owner,
               count(*) FILTER (WHERE tenure_before = 'renter' AND tenure = 'unknown') AS renter_to_unknown,
               count(*) FILTER (WHERE tenure_before = 'unknown' AND tenure = 'renter') AS unknown_to_renter
        FROM {finals} WHERE seen_before AND moved = false GROUP BY year ORDER BY year""").df()
    return out


def plot(t: dict[str, pd.DataFrame], n_cohort: int, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c, y, tc = t["cohort"], t["by_year"], t["tenure_changes"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.6))
    pctf = matplotlib.ticker.PercentFormatter(1.0)  # adds decimals when the range is narrow
    ax = axes[0, 0]
    if "cohort_found" in c and n_cohort:
        ax.plot(c["year"], c["cohort_found"] / n_cohort, "-o", ms=3, color="#333333", label="found anywhere")
        ax.plot(c["year"], c["cohort_in_study_states"] / n_cohort, "-o", ms=3, color="#1f5fa8", label="in NC/SC")
        ax.plot(c["year"], (c["cohort_found"] - c["cohort_in_study_states"]) / n_cohort, "-o", ms=3,
                color="#c8611c", label="in other states")
    ax.set_title(f"Households in NC/SC in {BASE_YEAR}: where they are")
    for ax, col, title, fmt in ((axes[0, 1], "owner_share", "Owner share (unknown codes count as renters)", pctf),
                                (axes[0, 2], "children_share", "Households with children", pctf),
                                (axes[1, 0], "median_income", "Median household income ($)",
                                 matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))):
        if f"cohort_{col}" in c:
            ax.plot(c["year"], c[f"cohort_{col}"], "-o", ms=3, color="#1f5fa8", label=f"{BASE_YEAR} households, wherever they live")
        ax.plot(c["year"], c[f"all_{col}"], "--", color="#888888", label="all households in NC/SC that year")
        ax.set_title(title)
        ax.yaxis.set_major_formatter(fmt)
    ax = axes[1, 1]
    ax.plot(y["year"], ratio(y["moved"], y["moved_known"]), "-o", ms=3, color="#333333", label="moved (new address)")
    ax.plot(y["year"], ratio(y["left_study"], y["in_study_before"]), "-o", ms=3, color="#c8611c", label="left NC/SC")
    ax.set_title("Moves since the year before")
    ax = axes[1, 2]
    ax.plot(tc["year"], ratio(tc["owner_to_renter"] + tc["owner_to_unknown"], tc["same_address"]), "-o", ms=3,
            color="#c8611c", label="owner -> renter or unknown")
    ax.plot(tc["year"], ratio(tc["renter_to_owner"] + tc["unknown_to_owner"], tc["same_address"]), "-o", ms=3,
            color="#1f5fa8", label="renter or unknown -> owner")
    ax.set_title("Tenure code changes, same address")
    for ax in axes.flat:
        if ax in (axes[1, 1], axes[1, 2], axes[0, 0]):
            ax.yaxis.set_major_formatter(pctf)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(steps=[1, 2, 5, 10]))
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle("Household panel: households ever in NC/SC, followed across the US", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    global FAM
    t0 = time.time()
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    states = geo.study_states()
    first = settings.PANEL_FIRST_YEAR
    years = [y for y in sorted(files) if not first or y >= first]
    if BASE_YEAR not in years:
        print(f"note: {BASE_YEAR} is not among the panel years {years[0]}-{years[-1]}")
    sig = panel.ids_signature(files, states)
    if panel.stored(panel.IDS_FAMILY) != sig or panel.stored(panel.IDS_PERSON) != sig:
        sys.exit("the panel IDs are missing or older than the converted files; run step 07 first")
    absent = [y for y in years if not panel.national_file(y).exists()]
    if absent:
        sys.exit(f"no step 07 file for {', '.join(map(str, absent))}; run step 07 first")
    shutil.rmtree(panel.WORK, ignore_errors=True)  # leftovers of a stopped run
    for d in (panel.WORK, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    for old in panel.DIR.glob("panel_*.parquet"):  # years no longer in the analysis
        m = re.fullmatch(r"panel_(\d{4})\.parquet", old.name)
        if m and int(m.group(1)) not in years:
            old.unlink()
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    geo.define_macros(con)
    if years != sorted(files):
        print(f"panel households: primary families in {'/'.join(states)} in {years[0]}-{years[-1]}", flush=True)
        FAM = panel_ids(con, files, years, states)

    # one year at a time: records, links from the year before, panel rows; only two
    # years of work files are kept on disk
    print("1/2 panel, year by year", flush=True)
    con.sql("CREATE OR REPLACE TEMP TABLE succ (fid VARCHAR, hhid VARCHAR, year INTEGER)")
    con.sql("CREATE OR REPLACE TEMP TABLE links (year INTEGER, fid VARCHAR, successor VARCHAR, kind VARCHAR)")
    con.sql("CREATE OR REPLACE TEMP TABLE seen (fid VARCHAR)")  # FAMILYIDs of the years done
    prev = None
    for y in years:
        n, n_out = year_rows(con, y, files[y], states)
        if prev is not None:
            link_pair(con, prev, y)
            drop_work(prev)
        final_year(con, y, prev)
        con.sql(f"INSERT INTO seen SELECT fid FROM read_parquet('{rows_file(y)}') "
                "WHERE fid NOT IN (SELECT fid FROM seen)")
        print(f"  {y}: {n:,} households ({n_out:,} outside the study states)", flush=True)
        prev = y
    drop_work(prev)
    con.sql(f"COPY links TO '{(panel.DIR / 'links.parquet').as_posix()}' (FORMAT parquet)")
    con.sql("DROP TABLE seen")
    notes = household_table(con, years)
    print("2/2 report", flush=True)
    t = report_tables(con, years)
    n_hh, n_linked, n_cohort, n_rows = con.sql(f"""
        SELECT count(*), count(*) FILTER (WHERE linked), count(*) FILTER (WHERE in_study_base),
               sum(n_years) FROM read_parquet('{(panel.DIR / 'households.parquet').as_posix()}')""").fetchall()[0]
    n_cohort = n_cohort or 0
    shutil.rmtree(panel.WORK, ignore_errors=True)

    for name, df in t.items():
        df.to_csv(TABLES / f"panel_{name}.csv", index=False)
    plot(t, n_cohort, FIGURES / "panel_trends.png")

    y, lk, c, tc = t["by_year"], t["links"], t["cohort"], t["tenure_changes"]
    where = pd.DataFrame({
        "year": y["year"], "households": y["households"].map("{:,}".format),
        "in NC/SC": y["in_study_states"].map("{:,}".format),
        "other states": ratio(y["other_states"], y["households"]).map(pct),
        "under a new FAMILYID": ratio(y["under_new_familyid"], y["households"]).map(pct)})
    moves = pd.DataFrame({
        "year": y["year"], "seen the year before": y["seen_before"].map("{:,}".format),
        "moved": ratio(y["moved"], y["moved_known"]).map(pct),
        "moved within NC/SC": ratio(y["moved_within"], y["in_study_before"]).map(pct),
        "left NC/SC": ratio(y["left_study"], y["in_study_before"]).map(pct),
        "came to NC/SC": ratio(y["entered_study"], y["outside_before"]).map(pct)}).iloc[1:]
    gone = lk.copy()
    for col in ("continues_new_familyid", "joined_other_household", "split", "adults_not_found"):
        gone[col] = ratio(lk[col], lk["not_found_by_familyid"]).map(pct)
    gone["not_found_by_familyid"] = lk["not_found_by_familyid"].map("{:,}".format)
    gone.columns = [col.replace("_", " ") for col in gone.columns]
    dest = t["destinations"].assign(households=lambda d: d["households"].map("{:,}".format),
                                    share=lambda d: d["share"].map(pct))
    dest = dest.rename(columns={"households_after_florence": f"of which {BASE_YEAR + 1}->{BASE_YEAR + 2}"})
    coh = pd.DataFrame({"year": c["year"]})
    if "cohort_found" in c and n_cohort:
        coh["found"] = (c["cohort_found"] / n_cohort).map(pct)
        coh["in NC/SC"] = (c["cohort_in_study_states"] / n_cohort).map(pct)
    for col, label, f in (("owner_share", "owner share", pct), ("children_share", "children", pct),
                          ("median_income", "median income", lambda v: "" if pd.isna(v) else f"{v:,.0f}")):
        if f"cohort_{col}" in c:
            coh[f"{label}: {BASE_YEAR} households"] = c[f"cohort_{col}"].map(f)
        coh[f"{label}: all in NC/SC"] = c[f"all_{col}"].map(f)
    ten = pd.DataFrame({"year": tc["year"], "same address": tc["same_address"].map("{:,}".format)})
    for col in tc.columns[2:]:
        ten[col.replace("_", " ")] = ratio(tc[col], tc["same_address"]).map(pct)

    REPORT.write_text("\n".join([
        "# Household panel (counts and shares only)", "",
        f"Households: every FAMILYID that is a primary family in {'/'.join(states)} in at least one year "
        f"{years[0]}-{years[-1]}, followed in every year it appears anywhere in the US (other states: "
        "step 07). When a FAMILYID disappears, its adults are looked up the next year: if they all turn "
        "up under one new FAMILYID that holds no one else, it continues the household. One row per "
        "household and year; with several records in a year, the primary-family record, then the most "
        "recent. Geography from the 2010 ALS codes. Figure: `output/figures/panel_trends.png`; tables: "
        "`output/tables/panel_*.csv`.", "",
        *([("Notes: " + "; ".join(notes)), ""] if notes else []),
        f"- households: {n_hh:,} ({n_linked:,} continue under a new FAMILYID at some point)",
        f"- household-years: {n_rows:,}",
        f"- households in {'/'.join(states)} in {BASE_YEAR} (the cohort below): {n_cohort:,}", "",
        "## Where the households are, by year", "",
        "other states: share of the year's households living outside the study states; under a new "
        "FAMILYID: share followed through a FAMILYID change.", "",
        *table(where),
        "## Households whose FAMILYID disappears", "",
        "Households in the previous year's files whose FAMILYID is not in this year's, and what their "
        "adults' records show: continues new FAMILYID (all adults under one new FAMILYID with no one "
        "else; the household is followed), joined another household, split across households, or "
        "adults not found anywhere.", "",
        *table(gone),
        "## Moves since the year before", "",
        "Households found in both years. moved: new address (street, unit and ZIP, or PO box / route), "
        "among households with an address in both years; moved within NC/SC and left NC/SC: among "
        "households in NC/SC the year before; came to NC/SC: among households elsewhere the year "
        "before.", "",
        *table(moves),
        "### Where households leaving NC/SC go", "",
        f"All years; the last column counts moves between the {BASE_YEAR + 1} and {BASE_YEAR + 2} files "
        f"(after Florence). States with fewer than {MIN_CELL} households are pooled.", "",
        *table(dest),
        f"## Households in NC/SC in {BASE_YEAR}, followed {years[0]}-{years[-1]}", "",
        f"found and in NC/SC: shares of the {n_cohort:,} households. The {BASE_YEAR} households are "
        "measured wherever they live that year; 'all in NC/SC' is every panel household living in "
        "NC/SC that year (the cross-section). Owner share: codes 7-9 among 0-9 (unknown codes count as "
        "renters, as in step 06).", "",
        *table(coh),
        "## Tenure code changes at the same address", "",
        "Households at the same address as the year before; share whose OWNER_RENTER_STATUS group "
        "changed. Jumps in single years point to Data Axle recoding rather than real changes.", "",
        *table(ten),
    ]))
    print(f"wrote {REPORT} ({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
