"""Step 2: bring the flood exposure data into Parquet.

TODO: once data_inventory.md shows the flood files' format and columns, keep
only the needed variables and build the merge key (e.g. 5-digit county FIPS,
11-digit tract GEOID, or lat/lon) here. The default below just converts every
CSV / Stata / Parquet file as-is.
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths  # noqa: E402


def main():
    paths.require(paths.FLOOD_EXPOSURE)
    con = duckdb.connect()
    for f in sorted(paths.FLOOD_EXPOSURE.rglob("*")):
        out = paths.FLOOD_CLEAN / f"{f.stem}.parquet"
        suffix = f.suffix.lower()
        if suffix == ".csv":
            con.sql(f"COPY (SELECT * FROM read_csv('{f.as_posix()}', all_varchar=true)) "
                    f"TO '{out.as_posix()}' (FORMAT parquet)")
        elif suffix == ".dta":
            pd.read_stata(f, convert_categoricals=False).to_parquet(out, index=False)
        elif suffix == ".parquet":
            con.sql(f"COPY (SELECT * FROM '{f.as_posix()}') TO '{out.as_posix()}' (FORMAT parquet)")
        else:
            continue
        print(f"{f.name} -> {out.name}")


if __name__ == "__main__":
    main()
