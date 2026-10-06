"""Step 3: merge infoUSA households with flood exposure, one file per year.

Builds 11-digit tract and 12-digit block-group GEOIDs from the infoUSA census
columns (geo_family in settings.yaml picks the column set) and left-joins the
tract and block-group flood measures. Writes
derived/merged/infousa_flood_<year>.parquet and output/logs/merge_report.md:
match rates under both column sets, geocode precision, FAMILYID uniqueness and
the formats of the code columns. The report has counts and shares only, so it
is safe to commit.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402

REPORT = paths.LOG_DIR / "merge_report.md"
FORMAT_COLS = ["STATE", "GE_CENSUS_STATE_2010", "GE_CENSUS_COUNTY", "GE_CENSUS_TRACT", "GE_CENSUS_BG",
               "GE_ALS_COUNTY_CODE_2010", "GE_ALS_CENSUS_TRACT_2010", "GE_ALS_CENSUS_BG_2010",
               "GE_CENSUS_LEVEL_2010", "GE_LATITUDE_2010", "GE_LONGITUDE_2010", "FAMILYID"]


def chosen_files() -> dict[int, Path]:
    """Converted file per year: the version settings.yaml prefers, else main."""
    versions = defaultdict(dict)
    for p in paths.INFOUSA_PARQUET.glob("infousa_*.parquet"):
        m = re.fullmatch(r"infousa_(\d{4})(?:_(.+))?\.parquet", p.name)
        if m:
            versions[int(m.group(1))][m.group(2) or "main"] = p
    files = {}
    for year in sorted(versions):
        want = settings.PREFER_VERSION.get(year, "main")
        if want in versions[year]:
            files[year] = versions[year][want]
        else:
            print(f"warning: {year} has no '{want}' version; skipped")
    return files


def table(df: pd.DataFrame) -> list[str]:
    return ["```", df.to_string(index=False), "```", ""]


def pct(x) -> str:
    return "" if x is None or pd.isna(x) else f"{100 * x:.1f}%"


def main() -> None:
    if settings.GEO_FAMILY not in geo.FAMILIES:
        sys.exit(f"geo_family in config/settings.yaml must be one of {list(geo.FAMILIES)}")
    files = chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    geo.define_macros(con)
    for level in ("tract", "bg"):
        f = paths.FLOOD_CLEAN / f"flood_{level}.parquet"
        con.sql(f"CREATE TABLE flood_{level} AS SELECT * FROM read_parquet('{f.as_posix()}')")
        n, ids = con.sql(f"SELECT count(*), count(DISTINCT {level}_geoid) FROM flood_{level}").fetchone()
        if n != ids:
            sys.exit(f"flood_{level} has duplicate GEOIDs; see output/logs/flood_clean.md")
    con.sql("CREATE TABLE covered AS SELECT DISTINCT left(tract_geoid, 5) AS county FROM flood_tract")
    n_counties = con.sql("SELECT count(*) FROM covered").fetchone()[0]

    fam = settings.GEO_FAMILY
    match, levels, ids = [], [], []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        out = paths.MERGED / f"infousa_flood_{year}.parquet"
        con.sql(f"""
            COPY (
                SELECT * FROM (SELECT *, {geo.tract_geoid(fam)} AS tract_geoid,
                                         {geo.bg_geoid(fam)} AS bg_geoid FROM {src})
                LEFT JOIN flood_tract USING (tract_geoid)
                LEFT JOIN flood_bg USING (bg_geoid)
            ) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        for family in geo.FAMILIES:
            r = con.sql(f"""
                SELECT count(*), count(h.t) / count(*), count(c.county) / count(*),
                       count(ft.tract_geoid) / nullif(count(c.county), 0),
                       count(fb.bg_geoid) / nullif(count(c.county), 0)
                FROM (SELECT {geo.tract_geoid(family)} AS t, {geo.bg_geoid(family)} AS b FROM {src}) h
                LEFT JOIN covered c ON left(h.t, 5) = c.county
                LEFT JOIN flood_tract ft ON h.t = ft.tract_geoid
                LEFT JOIN flood_bg fb ON h.b = fb.bg_geoid
            """).fetchone()
            match.append([year, family + (" (used)" if family == fam else ""), f"{r[0]:,}",
                          pct(r[1]), pct(r[2]), pct(r[3]), pct(r[4])])
        for value, n in con.sql(f"SELECT trim(GE_CENSUS_LEVEL_2010), count(*) FROM {src} GROUP BY 1").fetchall():
            levels.append((year, value, n))
        n, distinct, missing = con.sql(
            f"SELECT count(*), count(DISTINCT FAMILYID), count(*) - count(FAMILYID) FROM {src}").fetchone()
        ids.append([year, f"{n:,}", f"{distinct:,}", f"{n - missing - distinct:,}", f"{missing:,}"])
        print(f"{year}: merged -> {out.name}  ({match[-2][1]} tract match {match[-2][5]}, "
              f"{match[-1][1]} tract match {match[-1][5]})", flush=True)

    # Geocode precision: one column per code (codes longer than 4 characters shown as patterns)
    lv = pd.DataFrame(levels, columns=["year", "code", "n"])
    lv["code"] = lv["code"].fillna("(missing)").map(
        lambda v: v if len(v) <= 4 or v == "(missing)" else re.sub("[A-Za-z]", "A", re.sub(r"\d", "9", v)))
    lv = lv.groupby(["year", "code"], as_index=False)["n"].sum()
    top = lv.groupby("code")["n"].sum().nlargest(8).index
    lv.loc[~lv["code"].isin(top), "code"] = "other"
    lv = lv.pivot_table(index="year", columns="code", values="n", aggfunc="sum", fill_value=0)
    lv = lv.div(lv.sum(axis=1), axis=0).map(pct).reset_index()

    # Code formats across all years: 9 = digit, A = letter
    every = "read_parquet([" + ", ".join(f"'{p.as_posix()}'" for p in files.values()) + "], union_by_name=true)"
    total = con.sql(f"SELECT count(*) FROM {every}").fetchone()[0]
    fmt = []
    for col in FORMAT_COLS:
        rows = con.sql(f"""
            SELECT coalesce(regexp_replace(regexp_replace(trim("{col}"), '[0-9]', '9', 'g'),
                                           '[A-Za-z]', 'A', 'g'), '(missing)') AS pattern,
                   count(*) AS n, min(year), max(year)
            FROM {every} GROUP BY 1 ORDER BY n DESC LIMIT 5""").fetchall()
        for p, n, y0, y1 in rows:
            fmt.append([col, p or "(empty)", pct(n / total), f"{y0}-{y1}"])

    report = [
        "# Merge report (counts and shares only)", "",
        f"Merge keys built from the **{fam}** columns (geo_family in config/settings.yaml). "
        f"The flood tract file covers {n_counties} counties.", "",
        "## Match rates", "",
        "households: study-state households in the converted file. valid code: a well-formed "
        "tract code. in flood counties: the county appears in the flood data. tract / BG match: "
        "share of the in-county households whose tract / block group is in the flood data.", "",
        *table(pd.DataFrame(match, columns=["year", "columns", "households", "valid code",
                                            "in flood counties", "tract match", "BG match"])),
        "## Geocode precision (GE_CENSUS_LEVEL_2010, share of households)", "",
        *table(lv),
        "## FAMILYID", "",
        *table(pd.DataFrame(ids, columns=["year", "households", "distinct FAMILYID",
                                          "repeated", "missing"])),
        "## Code formats (9 = digit, A = letter; top 5 per column, all years)", "",
        *table(pd.DataFrame(fmt, columns=["column", "pattern", "share", "years"])),
    ]
    REPORT.write_text("\n".join(report))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
