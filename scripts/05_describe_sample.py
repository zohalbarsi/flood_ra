"""Step 5: describe the converted household records, year by year.

Writes output/logs/sample_report.md (counts and shares only, safe to commit)
to help choose sample restrictions: whether the two versions of a year hold
the same records (and which columns differ), families per address (by
dwelling type), adults listed in more than one family record, whether
FAMILYID follows families from one year to the next, the record-status
flags, geocode precision, how recently records were verified, and the
formats of key columns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, paths  # noqa: E402
from flood_ra.report import code_shares, mask, pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "sample_report.md"
FLAG_COLS = ["PRIMARY_FAMILY_IND", "HOUSEHOLDSTATUS", "LOCATION_TYPE", "ADDRESSTYPE", "VACANT",
             "USPSNOSTATS", "DOWNGRADE_REASON_CODE", "OWNER_RENTER_STATUS", "GE_CENSUS_LEVEL_2010"]
FORMAT_COLS = ["STATE", "GE_CENSUS_STATE_2010", "GE_CENSUS_COUNTY", "GE_CENSUS_TRACT", "GE_CENSUS_BG",
               "GE_ALS_COUNTY_CODE_2010", "GE_ALS_CENSUS_TRACT_2010", "GE_ALS_CENSUS_BG_2010",
               "GE_LATITUDE_2010", "GE_LONGITUDE_2010", "FAMILYID", "LOCATIONID",
               "RECENCY_DATE", "DOWNGRADE_DATE"]


def columns(con, f: Path) -> list[str]:
    return [r[0] for r in con.sql(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()]


def compare_versions(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per year with two versions: FAMILYIDs in both / one only, and the share
    of shared FAMILYIDs whose records are identical on every common column;
    plus, per differing column, how often the two versions agree."""
    rows, diffs = [], []
    for year, versions in paths.converted_versions().items():
        main = versions.get("main")
        for name, other in versions.items():
            if main is None or name == "main":
                continue
            shared = sorted((set(columns(con, main)) & set(columns(con, other))) - {"year", "source_file"})
            row = "md5(concat_ws('|', " + ", ".join(f"coalesce(\"{c}\", '')" for c in shared) + "))"
            both, only_main, only_other, same = con.sql(f"""
                SELECT count(*) FILTER (WHERE a.f IS NOT NULL AND b.f IS NOT NULL),
                       count(*) FILTER (WHERE b.f IS NULL), count(*) FILTER (WHERE a.f IS NULL),
                       count(*) FILTER (WHERE a.h = b.h)
                FROM (SELECT FAMILYID AS f, {row} AS h FROM read_parquet('{main.as_posix()}')) a
                FULL JOIN (SELECT FAMILYID AS f, {row} AS h FROM read_parquet('{other.as_posix()}')) b
                       ON a.f = b.f""").fetchone()
            rows.append([year, f"main vs {name}", f"{both:,}", f"{only_main:,}", f"{only_other:,}",
                         pct(same / both if both else None), len(shared)])
            diffs += column_differences(con, main, other, shared, year, name)
    return (pd.DataFrame(rows, columns=["year", "versions", "FAMILYID in both", "main only", "other only",
                                        "identical records", "columns compared"]),
            pd.DataFrame(diffs, columns=["year", "versions", "column", "same value", "distinct main",
                                         "distinct other", "missing main", "missing other"]))


def column_differences(con, main: Path, other: Path, shared: list[str], year: int, name: str) -> list[list]:
    """Columns whose values differ between two versions for the families in
    both. Finds them by comparing order-free checksums per column, then
    measures agreement family by family for the first 10 (the rest are
    listed by name only)."""
    sums = [con.sql("SELECT " + ", ".join(f'sum(hash("{c}"))' for c in shared)
                    + f" FROM read_parquet('{f.as_posix()}') WHERE FAMILYID IN "
                    f"(SELECT FAMILYID FROM read_parquet('{g.as_posix()}'))").fetchone()
            for f, g in ((main, other), (other, main))]  # families in both versions only
    differ = [c for c, x, y in zip(shared, *sums) if x != y]
    rows = []
    for c in differ[:10]:
        same, d_main, d_other, m_main, m_other = con.sql(f"""
            SELECT avg((a.v IS NOT DISTINCT FROM b.v)::INT), count(DISTINCT a.v), count(DISTINCT b.v),
                   count(*) FILTER (WHERE a.v IS NULL), count(*) FILTER (WHERE b.v IS NULL)
            FROM (SELECT FAMILYID AS f, "{c}" AS v FROM read_parquet('{main.as_posix()}')) a
            JOIN (SELECT FAMILYID AS f, "{c}" AS v FROM read_parquet('{other.as_posix()}')) b ON a.f = b.f
        """).fetchone()
        rows.append([year, f"main vs {name}", c, pct(same), f"{d_main:,}", f"{d_other:,}",
                     f"{m_main:,}", f"{m_other:,}"])
    for c in differ[10:]:
        rows.append([year, f"main vs {name}", c, "", "", "", "", ""])
    return rows


def families(con, files: dict[int, Path]) -> pd.DataFrame:
    rows = []
    for year, f in files.items():
        n, fam, loc = con.sql(f"SELECT count(*), count(DISTINCT FAMILYID), count(DISTINCT LOCATIONID) "
                              f"FROM read_parquet('{f.as_posix()}')").fetchone()
        rows.append([year, f"{n:,}", f"{fam:,}", f"{loc:,}", f"{n / loc:.2f}" if loc else ""])
    return pd.DataFrame(rows, columns=["year", "records", "distinct FAMILYID", "distinct LOCATIONID",
                                       "records per location"])


def dwelling_types(con, files: dict[int, Path]) -> pd.DataFrame:
    """Families per address and non-primary share in single-family (S) vs
    multi-family (M) dwellings, and at addresses with an apartment number."""
    rows = []
    for year, f in files.items():
        r = con.sql(f"""
            SELECT count(*) FILTER (WHERE lt = 'S') / nullif(count(DISTINCT loc) FILTER (WHERE lt = 'S'), 0),
                   count(*) FILTER (WHERE lt = 'M') / nullif(count(DISTINCT loc) FILTER (WHERE lt = 'M'), 0),
                   count(*) FILTER (WHERE unit) / nullif(count(DISTINCT loc) FILTER (WHERE unit), 0),
                   avg(CASE WHEN lt = 'S' THEN (NOT prim)::INT END),
                   avg(CASE WHEN lt = 'M' THEN (NOT prim)::INT END),
                   avg(CASE WHEN unit THEN (NOT prim)::INT END)
            FROM (SELECT trim(LOCATION_TYPE) AS lt, LOCATIONID AS loc,
                         coalesce(trim(PRIMARY_FAMILY_IND) = '1', false) AS prim,
                         coalesce(trim(UNIT_NUM), '') != '' AS unit
                  FROM read_parquet('{f.as_posix()}') WHERE LOCATIONID IS NOT NULL)""").fetchone()
        rows.append([year] + [f"{x:.2f}" if x is not None else "" for x in r[:3]] + [pct(x) for x in r[3:]])
    return pd.DataFrame(rows, columns=["year", "per address: S", "per address: M", "per address: apt no.",
                                       "non-primary: S", "non-primary: M", "non-primary: apt no."])


def people(con, files: dict[int, Path]) -> pd.DataFrame:
    """Adults (IndividualID_1-5) per year and state: how many there are, how
    many sit in primary families, how many are listed in 2+ family records,
    and how many adults of a non-primary family are also listed in the
    primary family at the same address."""
    rows = []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        fams = dict((st, (n, p)) for st, n, p in con.sql(
            f"SELECT upper(trim(STATE)), count(*), count(*) FILTER (WHERE trim(PRIMARY_FAMILY_IND) = '1') "
            f"FROM {src} GROUP BY 1").fetchall())
        slots = " UNION ALL ".join(
            f"SELECT FAMILYID AS f, LOCATIONID AS loc, upper(trim(STATE)) AS st, "
            f"coalesce(trim(PRIMARY_FAMILY_IND) = '1', false) AS prim, "
            f"nullif(trim(IndividualID_{k}), '') AS i FROM {src}" for k in range(1, 6))
        con.sql(f"CREATE OR REPLACE TEMP TABLE p AS SELECT * FROM ({slots}) WHERE i IS NOT NULL")
        for st, adults, prim_adults, multi, multi_same, nonprim, dup in con.sql("""
                WITH per AS (SELECT st, i, count(DISTINCT f) AS fams, count(DISTINCT loc) AS locs,
                                    bool_or(prim) AS in_prim, bool_or(NOT prim) AS in_nonprim
                             FROM p GROUP BY st, i),
                     dup AS (SELECT DISTINCT a.st, a.i FROM p a JOIN p b
                             ON a.i = b.i AND a.loc = b.loc AND a.f != b.f AND NOT a.prim AND b.prim)
                SELECT per.st, count(*), count(*) FILTER (WHERE in_prim), count(*) FILTER (WHERE fams > 1),
                       count(*) FILTER (WHERE fams > 1 AND locs = 1), count(*) FILTER (WHERE in_nonprim),
                       (SELECT count(*) FROM dup WHERE dup.st = per.st)
                FROM per GROUP BY per.st ORDER BY per.st""").fetchall():
            n, p = fams.get(st, (0, 0))
            rows.append([year, st, f"{n:,}", f"{p:,}", f"{adults:,}", f"{prim_adults:,}",
                         f"{prim_adults / p:.2f}" if p else "", pct(multi / adults if adults else None),
                         pct(multi_same / multi if multi else None), pct(dup / nonprim if nonprim else None)])
    return pd.DataFrame(rows, columns=["year", "state", "families", "primary families", "adults",
                                       "adults in primary families", "adults per primary family",
                                       "adults in 2+ families", "of those: one address",
                                       "non-primary adults also in the address's primary family"])


def continuity(con, files: dict[int, Path]) -> pd.DataFrame:
    """Primary families (PRIMARY_FAMILY_IND = 1) in one year: share found the
    next year under the same FAMILYID, at the same or a different LOCATIONID;
    and, of those not found, the share whose first person (IndividualID_1)
    appears in the next year's file under another FAMILYID."""
    rows = []
    years = sorted(files)
    for y0, y1 in zip(years, years[1:]):
        nxt = f"read_parquet('{files[y1].as_posix()}')"
        people = " UNION ALL ".join(f"SELECT IndividualID_{k} AS i FROM {nxt}" for k in range(1, 6))
        n, found, same, lost, relinked = con.sql(f"""
            WITH a AS (SELECT FAMILYID AS f, LOCATIONID AS loc, IndividualID_1 AS i
                       FROM read_parquet('{files[y0].as_posix()}') WHERE trim(PRIMARY_FAMILY_IND) = '1'),
                 b AS (SELECT FAMILYID AS f, LOCATIONID AS loc FROM {nxt}),
                 ids AS (SELECT DISTINCT i FROM ({people}) WHERE i IS NOT NULL)
            SELECT count(*), count(b.f), count(*) FILTER (WHERE a.loc = b.loc),
                   count(*) FILTER (WHERE b.f IS NULL),
                   count(*) FILTER (WHERE b.f IS NULL AND a.i IN (SELECT i FROM ids))
            FROM a LEFT JOIN b ON a.f = b.f""").fetchone()
        share = (lambda x: pct(x / n if n else None))
        rows.append([f"{y0}->{y1}", f"{n:,}", share(found), share(same), share(found - same), share(lost),
                     pct(relinked / lost if lost else None)])
    return pd.DataFrame(rows, columns=["years", "primary families", "found next year", "same location",
                                       "other location", "not found", "of not found: person found"])


def recency(con, files: dict[int, Path]) -> pd.DataFrame:
    """Years between the file year and the year RECENCY_DATE starts with
    (unparsed when the first four characters are not a plausible year)."""
    rows = []
    for year, f in files.items():
        r = con.sql(f"""
            WITH t AS (SELECT TRY_CAST(left(trim(RECENCY_DATE), 4) AS INTEGER) AS y
                       FROM read_parquet('{f.as_posix()}')),
                 a AS (SELECT CASE WHEN y BETWEEN 1950 AND {year} + 1 THEN {year} - y END AS age FROM t)
            SELECT count(*) FILTER (WHERE age <= 1), count(*) FILTER (WHERE age BETWEEN 2 AND 3),
                   count(*) FILTER (WHERE age BETWEEN 4 AND 6), count(*) FILTER (WHERE age >= 7),
                   count(*) FILTER (WHERE age IS NULL), count(*) FROM a""").fetchone()
        rows.append([year] + [pct(x / r[-1]) for x in r[:-1]])
    return pd.DataFrame(rows, columns=["year", "0-1 years", "2-3", "4-6", "7+", "unparsed or missing"])


def formats(con, files: dict[int, Path]) -> pd.DataFrame:
    """Top 5 value patterns per column across all years (9 = digit, A = letter)."""
    every = "read_parquet([" + ", ".join(f"'{p.as_posix()}'" for p in files.values()) + "], union_by_name=true)"
    total = con.sql(f"SELECT count(*) FROM {every}").fetchone()[0]
    rows = []
    for col in FORMAT_COLS:
        for p, n, y0, y1 in con.sql(f"""
                SELECT regexp_replace(regexp_replace(trim("{col}"), '[0-9]', '9', 'g'), '[A-Za-z]', 'A', 'g'),
                       count(*) AS n, min(year), max(year)
                FROM {every} GROUP BY 1 ORDER BY n DESC LIMIT 5""").fetchall():
            rows.append([col, mask(p), pct(n / total), f"{y0}-{y1}"])
    return pd.DataFrame(rows, columns=["column", "pattern", "share", "years"])


def main() -> None:
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    out = ["# Sample report (counts and shares only)", "",
           "Files used: " + ", ".join(f"{y} {f.stem.split('_', 2)[2] if f.stem.count('_') > 1 else 'main'}"
                                      for y, f in files.items()), ""]
    print("comparing versions", flush=True)
    versions, diffs = compare_versions(con)
    out += ["## Versions of the same year", "",
            "identical records: share of FAMILYIDs in both versions whose records match on every "
            "common column.", "", *table(versions)]
    if len(diffs):
        out += ["Columns that differ between versions (same value: share of shared families with "
                "the same value in both):", "", *table(diffs)]
    print("families and locations", flush=True)
    out += ["## Records, families and addresses", "",
            "records per location > 1 means several families share an address (LOCATIONID).", "",
            *table(families(con, files))]
    print("dwelling types", flush=True)
    out += ["### Families per address by dwelling type", "",
            "S = single-family, M = multi-family dwelling (LOCATION_TYPE); apt no. = addresses with an "
            "apartment number (UNIT_NUM). If multi-family addresses carry many more families than "
            "single-family ones, LOCATIONID marks buildings; if similar, it marks dwellings.", "",
            *table(dwelling_types(con, files))]
    print("people in more than one family", flush=True)
    out += ["## Adults and duplicate listings", "",
            "Adults are the IndividualID_1-5 slots (children are not listed). adults in 2+ families: "
            "listed in more than one family record that year; of those, the share whose records all "
            "share one address. Last column: adults of non-primary families who are also listed in the "
            "primary family at the same address (the same person counted twice). Compare adults with "
            "the Census adult population (18+) of each state.", "",
            *table(people(con, files))]
    print("year-to-year continuity", flush=True)
    out += ["## Families followed to the next year", "",
            "Base: primary families (PRIMARY_FAMILY_IND = 1). found next year: same FAMILYID in the "
            "next file (any record). other location: found at a different LOCATIONID (moved within "
            "the study states). not found: left the study states, or the record was dropped or re-keyed. "
            "of not found, person found: share of the not-found families whose IndividualID_1 is in the "
            "next file under another FAMILYID (a re-keyed or re-formed family).",
            "", *table(continuity(con, files))]
    out += ["## Record flags (share of records by code)", "",
            "Codes up to 4 characters shown as they are, longer values as patterns. "
            "The meaning of each code is in the Data Axle data dictionary.", ""]
    for col in FLAG_COLS:
        print(f"flags: {col}", flush=True)
        out += [f"### {col}", "", *table(code_shares(con, files, col))]
    print("recency and formats", flush=True)
    out += ["## Record recency (file year minus the year of RECENCY_DATE)", "", *table(recency(con, files))]
    out += ["## Code formats (9 = digit, A = letter; top 5 per column, all years)", "",
            *table(formats(con, files))]
    REPORT.write_text("\n".join(out))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
