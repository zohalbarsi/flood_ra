"""Step 4: merge infoUSA family records with flood exposure, one file per year.

Each row is one family record (FAMILYID): primary families and subfamilies
alike; PRIMARY_FAMILY_IND = 1 keeps one row per household (LOCATIONID).

Geography of each record (geo_family in settings.yaml picks the code columns):

- county_fips: the county code itself (not taken from the tract, so a record
  with an unknown tract keeps its county). If it is unknown: the Census 2000
  county code (files up to 2017 only), else the county of the block the
  coordinates fall in, if that block is in the record's state. county_source
  says which.
- tract_geoid: from the code. Only when it is unknown, the geocode is rooftop
  level (P) and the coordinates' block does not contradict the county code
  (or, without one, the state code), it comes from that block. bg_geoid: from
  the code; only when it is unknown, level P and the block lies in the
  record's tract, from the block. tract_source / bg_source.
- block_geoid: the block the coordinates fall in (step 03), always kept.
  Block flood measures are joined only when that block lies in the record's
  county; block_exposure_ok also requires a level-P geocode.
- county_fips_xy / tract_geoid_xy / bg_geoid_xy: the same geography from the
  coordinates alone, for checks.
- in_flood_counties: the county is covered by the flood data (NULL only when
  neither the county nor the coordinates are known). in_flood_counties_code
  and in_flood_counties_xy give the codes-only and coordinates-only answers.

Outside the flood counties the flood measures are missing, not zero. Writes
derived/merged/infousa_flood_<year>.parquet and output/logs/merge_report.md
(counts and shares only).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "merge_report.md"


def merge_sql(src: str, year: int, fam: str) -> str:
    """SELECT producing one year's merged rows."""
    county_2000 = geo.COUNTY_2000 if year <= geo.COUNTY_2000_LAST_YEAR else "NULL::VARCHAR"
    return f"""
        WITH h AS (
            SELECT *, {geo.county_fips(fam)} AS _county_code, {county_2000} AS _county_2000,
                      norm_state("{geo.FAMILIES[fam][0]}") AS _state_code,
                      {geo.tract_geoid(fam)} AS _tract_code, {geo.bg_geoid(fam)} AS _bg_code,
                      {geo.LATITUDE} AS latitude, {geo.LONGITUDE} AS longitude,
                      coalesce(upper(trim("GE_CENSUS_LEVEL_2010")) = 'P', false) AS level_p
            FROM {src}
        ), x AS (
            SELECT h.*, pb.block_geoid,
                   coalesce(_county_code, _county_2000) AS _county_codes,
                   -- the block's county may stand in only if it is in the record's state
                   pb.block_geoid IS NOT NULL AND coalesce(left(pb.block_geoid, 2) = _state_code, true) AS _xy_ok,
                   left(pb.block_geoid, 5) AS county_fips_xy,
                   left(pb.block_geoid, 11) AS tract_geoid_xy,
                   left(pb.block_geoid, 12) AS bg_geoid_xy
            FROM h LEFT JOIN point_blocks pb ON pb.latitude = h.latitude AND pb.longitude = h.longitude
        ), c AS (
            SELECT x.*,
                   coalesce(_county_codes, CASE WHEN _xy_ok THEN county_fips_xy END) AS county_fips,
                   CASE WHEN _county_code IS NOT NULL THEN 'code'
                        WHEN _county_2000 IS NOT NULL THEN '2000 code'
                        WHEN _xy_ok THEN 'coordinates' END AS county_source,
                   coalesce(_tract_code, CASE WHEN level_p AND coalesce(county_fips_xy = _county_codes, _xy_ok)
                                              THEN tract_geoid_xy END) AS tract_geoid
            FROM x
        ), g AS (
            SELECT c.*,
                   CASE WHEN _tract_code IS NOT NULL THEN 'code'
                        WHEN tract_geoid IS NOT NULL THEN 'coordinates' END AS tract_source,
                   coalesce(_bg_code, CASE WHEN level_p AND tract_geoid_xy = tract_geoid
                                           THEN bg_geoid_xy END) AS bg_geoid,
                   CASE WHEN block_geoid IS NOT NULL THEN coalesce(county_fips_xy = county_fips, false) END
                       AS block_in_county,
                   -- a plain equality key keeps the block join a hash join
                   CASE WHEN county_fips_xy = county_fips THEN block_geoid END AS _block_join
            FROM c
        )
        SELECT g.* EXCLUDE (_county_code, _county_2000, _county_codes, _tract_code, _bg_code,
                            _state_code, _xy_ok, _block_join,
                            latitude, longitude, level_p, block_geoid, county_fips, county_source,
                            tract_geoid, tract_source, bg_geoid, block_in_county,
                            county_fips_xy, tract_geoid_xy, bg_geoid_xy),
               g.county_fips, g.county_source, g.tract_geoid, g.tract_source,
               g.bg_geoid, CASE WHEN g._bg_code IS NOT NULL THEN 'code'
                                WHEN g.bg_geoid IS NOT NULL THEN 'coordinates' END AS bg_source,
               g.latitude, g.longitude, g.level_p, g.block_geoid, g.block_in_county,
               coalesce(g.block_in_county AND g.level_p, false) AS block_exposure_ok,
               g.county_fips_xy, g.tract_geoid_xy, g.bg_geoid_xy,
               CASE WHEN g.county_fips IS NOT NULL THEN g.county_fips IN (SELECT county FROM covered)
                    WHEN g.latitude IS NOT NULL AND g.longitude IS NOT NULL THEN false
                    END AS in_flood_counties,
               CASE WHEN g._county_codes IS NOT NULL
                    THEN g._county_codes IN (SELECT county FROM covered) END AS in_flood_counties_code,
               CASE WHEN g.latitude IS NOT NULL AND g.longitude IS NOT NULL
                    THEN g.block_geoid IS NOT NULL END AS in_flood_counties_xy,
               t.* EXCLUDE (tract_geoid), b.* EXCLUDE (bg_geoid), k.* EXCLUDE (block_geoid)
        FROM g
        LEFT JOIN flood_tract t ON t.tract_geoid = g.tract_geoid
        LEFT JOIN flood_bg b ON b.bg_geoid = g.bg_geoid
        LEFT JOIN flood_block k ON k.block_geoid = g._block_join
    """


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

    main_rows, member, sources, levels, columns = [], [], [], [], []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        out = paths.MERGED / f"infousa_flood_{year}.parquet"
        con.sql(f"COPY ({merge_sql(src, year, fam)}) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        version = f.stem.split("_", 2)[2] if f.stem.count("_") > 1 else "main"
        m = f"read_parquet('{out.as_posix()}')"
        cty = geo.county_fips(fam)
        via_tract = f"left({geo.tract_geoid(fam)}, 5)"
        r = con.sql(f"""
            SELECT count(*), count(*) FILTER (WHERE trim(PRIMARY_FAMILY_IND) = '1'),
                   count(*) FILTER (WHERE in_flood_counties),
                   count(tract_geoid) FILTER (WHERE in_flood_counties),
                   count(*) FILTER (WHERE in_flood_counties AND tract_geoid IN (SELECT tract_geoid FROM flood_tract)),
                   count(bg_geoid) FILTER (WHERE in_flood_counties),
                   count(*) FILTER (WHERE in_flood_counties AND bg_geoid IN (SELECT bg_geoid FROM flood_bg)),
                   count(block_geoid) FILTER (WHERE in_flood_counties),
                   count(*) FILTER (WHERE in_flood_counties AND block_exposure_ok),
                   -- membership by each rule
                   count({cty}),
                   count(*) FILTER (WHERE {cty} IN (SELECT county FROM covered)),
                   count(*) FILTER (WHERE {via_tract} IN (SELECT county FROM covered)),
                   count(*) FILTER (WHERE in_flood_counties_code),
                   count(*) FILTER (WHERE in_flood_counties_xy),
                   count(*) FILTER (WHERE in_flood_counties_code AND in_flood_counties_xy),
                   count(*) FILTER (WHERE in_flood_counties_code AND NOT in_flood_counties_xy),
                   count(*) FILTER (WHERE NOT in_flood_counties_code AND in_flood_counties_xy),
                   count(*) FILTER (WHERE in_flood_counties IS NULL),
                   -- sources, in the flood counties
                   count(*) FILTER (WHERE in_flood_counties AND county_source = 'code'),
                   count(*) FILTER (WHERE in_flood_counties AND county_source = '2000 code'),
                   count(*) FILTER (WHERE in_flood_counties AND county_source = 'coordinates'),
                   count(*) FILTER (WHERE in_flood_counties AND tract_source = 'code'),
                   count(*) FILTER (WHERE in_flood_counties AND tract_source = 'coordinates'),
                   count(*) FILTER (WHERE in_flood_counties AND tract_geoid IS NULL),
                   count(*) FILTER (WHERE in_flood_counties AND bg_source = 'coordinates'),
                   count(*) FILTER (WHERE block_geoid IS NOT NULL AND NOT block_in_county),
                   count(*) FILTER (WHERE block_geoid IS NOT NULL AND NOT block_in_county
                                    AND left(county_fips, 2) != left(block_geoid, 2))
            FROM {m}
        """).fetchone()
        (n, primary, inside, tract, tract_m, bg, bg_m, block, block_ok,
         cty_known, by_cty, by_tract, by_code, by_xy, both, code_only, xy_only, unknown,
         c_code, c_2000, c_xy, t_code, t_xy, t_none, bg_xy, blk_other, blk_state) = r
        share = (lambda x, d: pct(x / d if d else None))
        main_rows.append([year, version, f"{n:,}", f"{primary:,}", f"{inside:,}", share(tract, inside),
                          share(tract_m, inside), share(bg_m, inside), share(block, inside),
                          share(block_ok, inside)])
        member.append([year, f"{n:,}", share(n - cty_known, n), f"{by_cty:,}", f"{by_tract:,}",
                       f"{by_code:,}", f"{by_xy:,}", f"{both:,}", f"{code_only:,}", f"{xy_only:,}",
                       f"{inside:,}", f"{unknown:,}"])
        sources.append([year, f"{inside:,}", f"{c_2000:,}", f"{c_xy:,}", share(t_code, inside),
                        f"{t_xy:,}", f"{t_none:,}", f"{bg_xy:,}", f"{blk_other:,}", f"{blk_state:,}"])
        # tract code vs coordinates, by geocode level, in the flood counties
        for row in con.sql(f"""
            SELECT coalesce(nullif(upper(trim("GE_CENSUS_LEVEL_2010")), ''), '(blank)') AS lv, count(*),
                   count(*) FILTER (WHERE tract_source = 'code'),
                   count(tract_geoid_xy) FILTER (WHERE tract_source = 'code'),
                   count(*) FILTER (WHERE tract_source = 'code' AND tract_geoid_xy = tract_geoid),
                   count(bg_geoid_xy) FILTER (WHERE bg_source = 'code'),
                   count(*) FILTER (WHERE bg_source = 'code' AND bg_geoid_xy = bg_geoid)
            FROM {m} WHERE in_flood_counties GROUP BY lv
        """).fetchall():
            levels.append([year, row[0] if len(row[0]) <= 7 else "(other)", *row[1:]])
        for family in geo.FAMILIES:
            fc = con.sql(f"""
                SELECT count(t) / count(*),
                       count(ft.tract_geoid) / nullif(count(*) FILTER (WHERE left(t, 5) IN
                                                                  (SELECT county FROM covered)), 0)
                FROM (SELECT {geo.tract_geoid(family)} AS t FROM {src}) h
                LEFT JOIN flood_tract ft ON h.t = ft.tract_geoid
            """).fetchone()
            columns.append([year, family + (" (used)" if family == fam else ""), pct(fc[0]), pct(fc[1])])
        print(f"{year}: merged -> {out.name}  (in flood counties {inside:,}; tract measures "
              f"{share(tract_m, inside)}, block exposure ok {share(block_ok, inside)})", flush=True)

    lv = pd.DataFrame(levels, columns=["year", "level", "records", "tract_code", "found_t", "same_t",
                                       "found_b", "same_b"])
    lv["period"] = pd.cut(lv["year"], [0, 2017, 2019, 9999], labels=["2007-2017", "2018-2019", "2020-2025"])
    pooled = lv.groupby(["period", "level"], observed=True)[
        ["records", "tract_code", "found_t", "same_t", "found_b", "same_b"]].sum().reset_index()
    pooled = pooled[pooled["records"] > 0]
    share = (lambda x, d: pct(x / d if d else None))
    level_rows = [[r.period, r.level, f"{r.records:,}", share(r.tract_code, r.records),
                   share(r.found_t, r.tract_code), share(r.same_t, r.found_t), share(r.same_b, r.found_b)]
                  for r in pooled.itertuples(index=False)]

    REPORT.write_text("\n".join([
        "# Merge report (counts and shares only)", "",
        f"Geography from the **{fam}** code columns (geo_family in config/settings.yaml), with the "
        f"fallbacks described in scripts/04_merge.py. The flood tract file covers {n_counties} counties.", "",
        "family records: every family record in the study states (version: which file); primary "
        "families: PRIMARY_FAMILY_IND = 1, one per household. in flood counties: records whose "
        "county is covered by the flood data. The shares are of those: with a tract, with tract / "
        "block-group flood measures, placed in a block, and with block exposure usable "
        "(block_exposure_ok: rooftop-level geocode and the block lies in the record's county).", "",
        *table(pd.DataFrame(main_rows, columns=["year", "version", "family records", "primary families",
                                                "in flood counties", "tract", "tract measures",
                                                "BG measures", "in a block", "block exposure ok"])),
        "## Who is in the flood counties, by each rule", "",
        "no county code: share of records whose county code is unknown (000 or blank). Counts of "
        "records in the flood counties by: county code: the county code itself; via tract: the "
        "county part of the tract GEOID (the rule before this fix, which loses records whose tract "
        "is 000000); codes: the county code, else the Census 2000 county code up to 2017; "
        "coordinates: the point falls in a flood-county block. both / codes only / coordinates "
        "only compare the last two among records with both a county code and coordinates. "
        "chosen: in_flood_counties (codes, else coordinates); unknown: neither is known.", "",
        *table(pd.DataFrame(member, columns=["year", "family records", "no county code", "county code",
                                             "via tract", "codes", "coordinates", "both", "codes only",
                                             "coordinates only", "chosen", "unknown"])),
        "## Where each record's geography comes from (records in the flood counties)", "",
        "county from 2000 code / coordinates: the county code was unknown. tract from code: share "
        "with a valid tract code. tract from coordinates: tract code unknown, filled from the "
        "block (level P, block not in another county). no tract: still unknown. BG from "
        "coordinates: block-group code unknown, filled from a level-P block in the record's tract. Last two columns, all "
        "records: the block from the coordinates lies outside the record's county (its block "
        "measures are not joined), and of those, in another state.", "",
        *table(pd.DataFrame(sources, columns=["year", "in flood counties", "county from 2000 code",
                                              "county from coordinates", "tract from code",
                                              "tract from coordinates", "no tract", "BG from coordinates",
                                              "block outside county", "block in another state"])),
        "## Codes vs coordinates, by geocode level (records in the flood counties)", "",
        "GE_CENSUS_LEVEL_2010 (the dictionary gives no codes; P is taken as rooftop level), "
        "years pooled by period. tract code: share with a valid tract code. in a block: share of "
        "those whose coordinates fall in a block. same tract / same BG: share of those whose block "
        "lies in the record's tract / block group (BG: among records with a block-group code).", "",
        *table(pd.DataFrame(level_rows, columns=["years", "level", "records", "tract code", "in a block",
                                                 "same tract", "same BG"])),
        "## Tract codes under each column set", "",
        "valid code: share of all records with a well-formed tract code. tract match: share of the "
        "records whose tract-code county is a flood county that match a flood tract.", "",
        *table(pd.DataFrame(columns, columns=["year", "columns", "valid code", "tract match"])),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
