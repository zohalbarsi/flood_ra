"""Step 2: clean the Hurricane Florence flood exposure files.

For each geography (tract, block group, block) builds the zero-padded Census
GEOID from its parts and keeps the flood measures, renamed with the level as
a prefix (tract_pct_flooded_gfd, bg_pct_flooded_gfd, ...) so the levels can
sit side by side after the merge. Writes derived/flood_clean/flood_<level>.parquet
and output/logs/flood_clean.md: rows, unique IDs, IDs that disagree with the
file's own GEOID column, areas per state, and missing flood shares.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, paths, settings  # noqa: E402

# level: (suffix of its Census ID columns, the sub-tract part of the ID, its width)
LEVELS = {
    "tract": ("", None, 0),
    "bg": ("", "BLKGRPCE", 1),
    "block": ("10", "BLOCKCE10", 4),
}
MEASURE = re.compile(r"^(flooded_pixel_count|total_pixel_count|flooded_area_m2|pct_flooded)_")


def pad(col: str, width: int) -> str:
    """SQL: column as a zero-padded code of the given width."""
    return f"right('{'0' * width}' || trim(\"{col}\"), {width})"


def main() -> None:
    paths.require(paths.FLOOD_EXPOSURE)
    con = db.connect()
    log = ["# Flood exposure files (counts only)", ""]
    for level, (sfx, sub, width) in LEVELS.items():
        f = paths.FLOOD_EXPOSURE / settings.FLOOD_FILES[level]
        src = f"read_csv('{f.as_posix()}', all_varchar=true, header=true)"
        cols = [r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {src}").fetchall()]
        parts = [pad(f"STATEFP{sfx}", 2), pad(f"COUNTYFP{sfx}", 3), pad(f"TRACTCE{sfx}", 6)]
        geoid = " || ".join(parts + ([pad(sub, width)] if sub else []))
        n_digits = 11 + width
        measures = [c for c in cols if MEASURE.match(c)]
        shares = [c for c in measures if c.startswith("pct_")]
        con.sql(f"CREATE OR REPLACE TABLE src AS SELECT {geoid} AS geoid, * FROM {src}")
        select = [f"geoid AS {level}_geoid", f'TRY_CAST("ALAND{sfx}" AS DOUBLE) AS {level}_aland_m2']
        select += [f'TRY_CAST("{c}" AS DOUBLE) AS "{level}_{c}"' for c in measures]
        out = paths.FLOOD_CLEAN / f"flood_{level}.parquet"
        con.sql(f"COPY (SELECT {', '.join(select)} FROM src) TO '{out.as_posix()}' (FORMAT parquet)")

        rows, ids, bad, differ = con.sql(f"""
            SELECT count(*), count(DISTINCT geoid),
                   count(*) FILTER (WHERE geoid IS NULL OR NOT regexp_full_match(geoid, '[0-9]{{{n_digits}}}')),
                   count(*) FILTER (WHERE {pad(f'GEOID{sfx}', n_digits)} != geoid)
            FROM src""").fetchone()
        states = con.sql("SELECT left(geoid, 2), count(*) FROM src GROUP BY 1 ORDER BY 1").fetchall()
        missing = con.sql("SELECT " + ", ".join(
            f'count(*) FILTER (WHERE TRY_CAST("{c}" AS DOUBLE) IS NULL)' for c in shares) + " FROM src").fetchone()
        log += [f"## {level}: `{f.name}`", "",
                f"- rows {rows:,}; unique GEOIDs {ids:,}"
                + ("" if rows == ids else " **(duplicates: the merge would repeat households)**"),
                f"- malformed GEOIDs {bad:,}; GEOIDs that differ from the file's GEOID{sfx} column {differ:,}",
                "- areas by state FIPS: " + ", ".join(f"{s}: {n:,}" for s, n in states),
                "- missing flood shares: " + ", ".join(f"{c} {n:,}" for c, n in zip(shares, missing)),
                ""]
        print(f"{level}: {rows:,} areas -> {out.name}")
    (paths.LOG_DIR / "flood_clean.md").write_text("\n".join(log))


if __name__ == "__main__":
    main()
