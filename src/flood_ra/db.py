"""DuckDB connections sized by the resources in config/paths.yaml."""
from __future__ import annotations

import duckdb

from flood_ra import paths


def connect(threads: int = paths.THREADS) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql(f"SET threads = {threads}")
    con.sql(f"SET memory_limit = '{paths.MEMORY}'")
    con.sql("SET preserve_insertion_order = false")  # lets large copies stream
    con.sql(f"SET temp_directory = '{paths.DUCKDB_TMP.as_posix()}'")
    return con
