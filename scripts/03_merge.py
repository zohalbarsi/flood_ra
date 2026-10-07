"""Step 3: merge infoUSA households with flood exposure, one file per year.

Builds 11-digit tract and 12-digit block-group GEOIDs from the infoUSA census
columns (geo_family in settings.yaml picks the column set) and left-joins the
tract and block-group flood measures. Adds in_flood_counties: whether the
household's county is covered by the flood data. Outside those counties the
flood measures are missing, not zero. Writes
derived/merged/infousa_flood_<year>.parquet and output/logs/merge_report.md
with match rates under both column sets (counts and shares only).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "merge_report.md"


def main() -> None:
    fam = settings.GEO_FAMILY
    if fam not in geo.FAMILIES:
        sys.exit(f"geo_family in config/settings.yaml must be one of {list(geo.FAMILIES)}")
    files = paths.chosen_files()
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

    match = []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        out = paths.MERGED / f"infousa_flood_{year}.parquet"
        con.sql(f"""
            COPY (
                SELECT h.*,
                       CASE WHEN h.tract_geoid IS NOT NULL THEN c.county IS NOT NULL END AS in_flood_counties,
                       t.* EXCLUDE (tract_geoid), b.* EXCLUDE (bg_geoid)
                FROM (SELECT *, {geo.tract_geoid(fam)} AS tract_geoid,
                                {geo.bg_geoid(fam)} AS bg_geoid FROM {src}) h
                LEFT JOIN covered c ON left(h.tract_geoid, 5) = c.county
                LEFT JOIN flood_tract t ON t.tract_geoid = h.tract_geoid
                LEFT JOIN flood_bg b ON b.bg_geoid = h.bg_geoid
            ) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        version = f.stem.split("_", 2)[2] if f.stem.count("_") > 1 else "main"
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
            match.append([year, version, family + (" (used)" if family == fam else ""), f"{r[0]:,}",
                          pct(r[1]), pct(r[2]), pct(r[3]), pct(r[4])])
        used = next(m for m in match[-len(geo.FAMILIES):] if m[2].endswith("(used)"))
        print(f"{year}: merged -> {out.name}  (in flood counties {used[5]}, "
              f"tract match {used[6]}, BG match {used[7]})", flush=True)

    REPORT.write_text("\n".join([
        "# Merge report (counts and shares only)", "",
        f"Merge keys built from the **{fam}** columns (geo_family in config/settings.yaml). "
        f"The flood tract file covers {n_counties} counties.", "",
        "households: study-state households in the converted file (version: which file). "
        "valid code: a well-formed tract code. in flood counties: the county appears in the "
        "flood data. tract / BG match: share of the in-county households whose tract / block "
        "group is in the flood data.", "",
        *table(pd.DataFrame(match, columns=["year", "version", "columns", "households", "valid code",
                                            "in flood counties", "tract match", "BG match"])),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
