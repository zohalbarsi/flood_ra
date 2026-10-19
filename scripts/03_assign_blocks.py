"""Step 3: place each family record in a 2010 census block, by its coordinates.

infoUSA has no block code, so this step finds the flood file's block outline
that contains each household's coordinates (GE_LATITUDE_2010 /
GE_LONGITUDE_2010). It works on the distinct coordinates of all years at once,
only those inside the outlines' bounding box, and writes the lookup
derived/geo/point_blocks.parquet (latitude, longitude -> block_geoid) that the
merge uses. A point exactly on the line between two blocks goes to the lower
GEOID. output/logs/block_assignment.md checks the blocks against each
household's census tract and block-group codes, by geocode level (counts and
shares only).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "block_assignment.md"
CHUNK = 1_000_000  # points per spatial join, to bound memory


def place(points: pd.DataFrame, blocks: gpd.GeoDataFrame) -> tuple[pd.DataFrame, int]:
    """Block of each point; returns the lookup and the number of boundary points."""
    found = []
    for start in range(0, len(points), CHUNK):
        chunk = points.iloc[start:start + CHUNK]
        pts = gpd.GeoDataFrame(chunk, geometry=gpd.points_from_xy(chunk["longitude"], chunk["latitude"]),
                               crs=4326)
        hit = gpd.sjoin(pts, blocks, how="inner", predicate="intersects")
        found.append(pd.DataFrame(hit[["latitude", "longitude", "block_geoid"]]))
        print(f"  {min(start + CHUNK, len(points)):,} of {len(points):,} coordinates placed", flush=True)
    found = (pd.concat(found, ignore_index=True) if found
             else pd.DataFrame({"latitude": [], "longitude": [], "block_geoid": []}))
    boundary = int(found.duplicated(["latitude", "longitude"]).sum())
    lookup = found.sort_values("block_geoid").drop_duplicates(["latitude", "longitude"])
    return lookup, boundary


def main() -> None:
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    if not paths.BLOCK_POLYGONS.exists():
        sys.exit(f"{paths.BLOCK_POLYGONS} not found; run step 02 first")
    t0 = time.time()
    blocks = gpd.read_parquet(paths.BLOCK_POLYGONS)
    minx, miny, maxx, maxy = blocks.total_bounds
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    geo.define_macros(con)

    every = "read_parquet([" + ", ".join(f"'{p.as_posix()}'" for p in files.values()) + "], union_by_name=true)"
    points = con.sql(f"""
        SELECT DISTINCT latitude, longitude
        FROM (SELECT {geo.LATITUDE} AS latitude, {geo.LONGITUDE} AS longitude FROM {every})
        WHERE latitude BETWEEN {miny} AND {maxy} AND longitude BETWEEN {minx} AND {maxx}
    """).df()
    print(f"{len(blocks):,} blocks; {len(points):,} distinct household coordinates in their "
          "bounding box", flush=True)
    lookup, boundary = place(points, blocks)
    lookup.to_parquet(paths.POINT_BLOCKS, index=False)
    print(f"{len(lookup):,} coordinates in a block -> {paths.POINT_BLOCKS.name}", flush=True)

    # Check against the households' census codes, in the counties the flood data cover
    fam = settings.GEO_FAMILY
    con.sql(f"CREATE TABLE pb AS SELECT * FROM read_parquet('{paths.POINT_BLOCKS.as_posix()}')")
    con.sql("CREATE TABLE covered AS SELECT DISTINCT left(tract_geoid, 5) AS county FROM "
            f"read_parquet('{(paths.FLOOD_CLEAN / 'flood_tract.parquet').as_posix()}')")
    rows, membership = [], []
    for year, f in files.items():
        r = con.sql(f"""
            WITH h AS (SELECT {geo.tract_geoid(fam)} AS t, {geo.bg_geoid(fam)} AS b,
                              {geo.LATITUDE} AS latitude, {geo.LONGITUDE} AS longitude,
                              coalesce(trim(GE_CENSUS_LEVEL_2010) = 'P', false) AS level_p
                       FROM read_parquet('{f.as_posix()}')),
                 c AS (SELECT * FROM h WHERE left(t, 5) IN (SELECT county FROM covered))
            SELECT count(*),
                   count(*) FILTER (WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL),
                   count(pb.block_geoid),
                   count(*) FILTER (WHERE left(pb.block_geoid, 11) = c.t),
                   count(*) FILTER (WHERE left(pb.block_geoid, 12) = c.b),
                   count(pb.block_geoid) FILTER (WHERE level_p),
                   count(*) FILTER (WHERE level_p AND left(pb.block_geoid, 11) = c.t),
                   count(pb.block_geoid) FILTER (WHERE NOT level_p),
                   count(*) FILTER (WHERE NOT level_p AND left(pb.block_geoid, 11) = c.t)
            FROM c LEFT JOIN pb ON pb.latitude = c.latitude AND pb.longitude = c.longitude
        """).fetchone()
        n, coords, found, tract, bg, found_p, tract_p, found_o, tract_o = r
        share = (lambda x, d: pct(x / d if d else None))
        rows.append([year, f"{n:,}", share(coords, n), share(found, n), share(tract, found),
                     share(bg, found), share(tract_p, found_p), share(tract_o, found_o)])

        # Who is in the flood counties: by the merge-key county code, by the 2000
        # county code, or by coordinates (a point in a flood block)?
        codes, xy, both, c2000, c2000_xy = con.sql(f"""
            WITH h AS (SELECT left({geo.tract_geoid(fam)}, 5) AS cty,
                              norm_state("GE_CENSUS_STATE_2010") || norm_county("GE_CENSUS_COUNTY") AS cty2000,
                              {geo.LATITUDE} AS latitude, {geo.LONGITUDE} AS longitude
                       FROM read_parquet('{f.as_posix()}'))
            SELECT count(*) FILTER (WHERE cty IN (SELECT county FROM covered)),
                   count(pb.block_geoid),
                   count(pb.block_geoid) FILTER (WHERE cty IN (SELECT county FROM covered)),
                   count(*) FILTER (WHERE cty2000 IN (SELECT county FROM covered)),
                   count(pb.block_geoid) FILTER (WHERE cty2000 IN (SELECT county FROM covered))
            FROM h LEFT JOIN pb ON pb.latitude = h.latitude AND pb.longitude = h.longitude
        """).fetchone()
        membership.append([year, f"{codes:,}", f"{xy:,}", f"{both:,}", f"{codes - both:,}", f"{xy - both:,}",
                           f"{c2000:,}" if c2000 else "", f"{xy - c2000_xy:,}" if c2000 else ""])

    minutes = (time.time() - t0) / 60
    REPORT.write_text("\n".join([
        "# Block assignment (counts and shares only)", "",
        f"{len(blocks):,} block outlines; {len(points):,} distinct household coordinates in their "
        f"bounding box (all years); {len(lookup):,} fall in a block, {boundary:,} of them on a line "
        f"between blocks (given the lower GEOID). {minutes:.1f} minutes.", "",
        f"Family records (primary families and subfamilies) whose county ({fam} codes) is "
        "covered by the flood data. coordinates: "
        "usable latitude and longitude. in a block: the coordinates fall in a block outline. "
        "same tract / same BG: the block lies in the household's census tract / block group "
        "(share of those in a block); level P / other levels split that by GE_CENSUS_LEVEL_2010.", "",
        *table(pd.DataFrame(rows, columns=["year", "family records", "coordinates", "in a block", "same tract",
                                           "same BG", "same tract, level P", "same tract, other levels"])),
        "## Flood-county membership: county codes vs coordinates", "",
        f"All family records. by code: county ({fam} codes, the merge key) is a flood county. "
        "by coordinates: the point falls in a flood-county block. code only / coordinates only: "
        "in one but not the other. 2000 code: the Census 2000 county code (GE_CENSUS_COUNTY, "
        "empty from 2018) is a flood county; last column: in a flood block but not by the 2000 code.", "",
        *table(pd.DataFrame(membership, columns=["year", "by code", "by coordinates", "both", "code only",
                                                 "coordinates only", "by 2000 code",
                                                 "coordinates only vs 2000 code"])),
    ]))
    print(f"wrote {REPORT} ({minutes:.1f} min)")


if __name__ == "__main__":
    main()
