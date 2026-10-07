"""Step 4: describe the converted household records, year by year.

Writes output/logs/sample_report.md (counts and shares only, safe to commit)
to help choose sample restrictions: whether the two versions of a year hold
the same records, families per address, the record-status flags, geocode
precision, how recently records were verified, and the formats of key columns.
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


def compare_versions(con) -> pd.DataFrame:
    """Per year with two versions: FAMILYIDs in both / one only, and the share
    of shared FAMILYIDs whose records are identical on every common column."""
    rows = []
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
    return pd.DataFrame(rows, columns=["year", "versions", "FAMILYID in both", "main only", "other only",
                                       "identical records", "columns compared"])


def families(con, files: dict[int, Path]) -> pd.DataFrame:
    rows = []
    for year, f in files.items():
        n, fam, loc = con.sql(f"SELECT count(*), count(DISTINCT FAMILYID), count(DISTINCT LOCATIONID) "
                              f"FROM read_parquet('{f.as_posix()}')").fetchone()
        rows.append([year, f"{n:,}", f"{fam:,}", f"{loc:,}", f"{n / loc:.2f}" if loc else ""])
    return pd.DataFrame(rows, columns=["year", "records", "distinct FAMILYID", "distinct LOCATIONID",
                                       "records per location"])


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
    out += ["## Versions of the same year", "",
            "identical records: share of FAMILYIDs in both versions whose records match on every "
            "common column.", "", *table(compare_versions(con))]
    print("families and locations", flush=True)
    out += ["## Records, families and addresses", "",
            "records per location > 1 means several families share an address (LOCATIONID).", "",
            *table(families(con, files))]
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
