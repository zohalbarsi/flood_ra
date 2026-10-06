"""Step 1: convert each raw infoUSA file to Parquet, once.

Raw files are read in place and never modified. DuckDB streams the CSV, so
files larger than RAM are fine. All columns are read as text so IDs (ABI,
ZIP, FIPS) keep their leading zeros; cast types in later steps. Files already
converted are skipped, so re-running is cheap.
"""
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths  # noqa: E402


def main(overwrite: bool = False):
    con = duckdb.connect()
    con.sql("SET preserve_insertion_order = false")  # lower memory use
    files = sorted(paths.INFOUSA_RAW.glob(paths.INFOUSA_GLOB))
    if not files:
        sys.exit(f"no files match {paths.INFOUSA_GLOB} in {paths.INFOUSA_RAW}")
    for f in files:
        out = paths.INFOUSA_PARQUET / f"{f.stem}.parquet"
        if out.exists() and not overwrite:
            print(f"skip {f.name} (done)")
            continue
        t = time.time()
        tmp = out.with_suffix(".parquet.tmp")
        con.sql(f"""
            COPY (
                SELECT *, '{f.name}' AS source_file
                FROM read_csv('{f.as_posix()}', all_varchar=true,
                              delim='{paths.INFOUSA_DELIM}', header=true,
                              sample_size=-1, ignore_errors=false)
            ) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        tmp.replace(out)  # only a finished file gets the final name
        n = con.sql(f"SELECT count(*) FROM '{out.as_posix()}'").fetchone()[0]
        print(f"{f.name}: {n:,} rows in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main(overwrite="--overwrite" in sys.argv)
