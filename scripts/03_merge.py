"""Step 3: merge infoUSA establishments with flood exposure.

TODO: set the key columns once data_inventory.md shows both schemas. DuckDB
queries the Parquet folders directly, so the join never loads everything into
pandas. The match-rate report goes to output/logs (safe to commit).
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths  # noqa: E402

INFOUSA_KEY = "TODO_infousa_geo_column"   # e.g. county FIPS / census tract
FLOOD_KEY = "TODO_flood_geo_column"


def main():
    if "TODO" in INFOUSA_KEY + FLOOD_KEY:
        sys.exit("set INFOUSA_KEY and FLOOD_KEY in scripts/03_merge.py first")
    con = duckdb.connect()
    con.sql(f"CREATE VIEW infousa AS SELECT * FROM '{(paths.INFOUSA_PARQUET / '*.parquet').as_posix()}'")
    con.sql(f"CREATE VIEW flood AS SELECT * FROM '{(paths.FLOOD_CLEAN / '*.parquet').as_posix()}'")
    out = paths.MERGED / "infousa_flood.parquet"
    con.sql(f"""
        COPY (
            SELECT i.*, f.* EXCLUDE ({FLOOD_KEY}), f.{FLOOD_KEY} IS NOT NULL AS _matched
            FROM infousa i
            LEFT JOIN flood f ON i.{INFOUSA_KEY} = f.{FLOOD_KEY}
        ) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    report = con.sql(f"""
        SELECT source_file, count(*) AS n, avg(_matched::INT) AS match_rate
        FROM '{out.as_posix()}' GROUP BY 1 ORDER BY 1
    """).df()
    (paths.LOG_DIR / "merge_report.txt").write_text(report.to_string(index=False))
    print(report)


if __name__ == "__main__":
    main()
