"""Step 4: merge infoUSA family records with flood exposure, one file per year.

Each row is one family record (FAMILYID): primary families and subfamilies
alike; PRIMARY_FAMILY_IND = 1 keeps one row per household (LOCATIONID).

Builds 11-digit tract and 12-digit block-group GEOIDs from the infoUSA census
columns (geo_family in settings.yaml picks the column set) and left-joins the
tract and block-group flood measures. Adds the household's census block from
step 03 (block_geoid, via its coordinates) with the block flood measures,
latitude and longitude as numbers, and in_flood_counties: whether the
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
    if not paths.POINT_BLOCKS.exists():
        sys.exit(f"{paths.POINT_BLOCKS} not found; run step 03 first")
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    geo.define_macros(con)
    con.sql(f"CREATE TABLE point_blocks AS SELECT * FROM read_parquet('{paths.POINT_BLOCKS.as_posix()}')")
    for level in ("tract", "bg", "block"):
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
                       pb.block_geoid,
                       t.* EXCLUDE (tract_geoid), b.* EXCLUDE (bg_geoid), k.* EXCLUDE (block_geoid)
                FROM (SELECT *, {geo.tract_geoid(fam)} AS tract_geoid, {geo.bg_geoid(fam)} AS bg_geoid,
                                {geo.LATITUDE} AS latitude, {geo.LONGITUDE} AS longitude FROM {src}) h
                LEFT JOIN covered c ON left(h.tract_geoid, 5) = c.county
                LEFT JOIN flood_tract t ON t.tract_geoid = h.tract_geoid
                LEFT JOIN flood_bg b ON b.bg_geoid = h.bg_geoid
                LEFT JOIN point_blocks pb ON pb.latitude = h.latitude AND pb.longitude = h.longitude
                LEFT JOIN flood_block k ON k.block_geoid = pb.block_geoid
            ) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        block = con.sql("SELECT count(block_geoid) FILTER (WHERE in_flood_counties) / "
                        "nullif(count(*) FILTER (WHERE in_flood_counties), 0) "
                        f"FROM read_parquet('{out.as_posix()}')").fetchone()[0]
        primary = con.sql(f"SELECT count(*) FILTER (WHERE trim(PRIMARY_FAMILY_IND) = '1') "
                          f"FROM {src}").fetchone()[0]
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
                          f"{primary:,}", pct(r[1]), pct(r[2]), pct(r[3]), pct(r[4]), pct(block) if family == fam else ""])
        used = next(m for m in match[-len(geo.FAMILIES):] if m[2].endswith("(used)"))
        print(f"{year}: merged -> {out.name}  (in flood counties {used[6]}, "
              f"tract match {used[7]}, BG match {used[8]}, block found {used[9]})", flush=True)

    REPORT.write_text("\n".join([
        "# Merge report (counts and shares only)", "",
        f"Merge keys built from the **{fam}** columns (geo_family in config/settings.yaml). "
        f"The flood tract file covers {n_counties} counties.", "",
        "family records: every family record in the study states (version: which file), "
        "primary families and subfamilies alike; primary families: those with "
        "PRIMARY_FAMILY_IND = 1, one per household. Shares are of all family records. valid code: "
        "a well-formed tract code. in flood counties: the county appears in the flood data. "
        "tract / BG match: share of the in-county records whose tract / block group is in the "
        "flood data. block found: share of the in-county records placed in a block by step 03 "
        "(details in block_assignment.md).", "",
        *table(pd.DataFrame(match, columns=["year", "version", "columns", "family records",
                                            "primary families", "valid code",
                                            "in flood counties", "tract match", "BG match", "block found"])),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
