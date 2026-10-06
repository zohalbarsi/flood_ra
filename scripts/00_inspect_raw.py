"""Step 0: inventory the raw data on the server WITHOUT copying any of it.

Writes output/logs/data_inventory.md: file names, sizes, and column
names/types for every infoUSA file and every file in the flood_exposure folder.
The report holds no data values, so it is safe to commit and share; it is how
code written elsewhere learns the schema of data that never leaves the server.
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths  # noqa: E402

TABULAR = {".csv", ".txt", ".gz", ".parquet", ".dta"}


def describe(con, f: Path, delim: str | None = None) -> str:
    try:
        if f.suffix == ".parquet":
            rel = f"read_parquet('{f.as_posix()}')"
        elif f.suffix == ".dta":
            import pandas as pd
            it = pd.read_stata(f, iterator=True)
            return "\n".join(f"  - `{c}`" for c in it.varlist)
        else:
            d = f", delim='{delim}'" if delim else ""
            rel = f"read_csv('{f.as_posix()}', all_varchar=true, sample_size=20000{d})"
        cols = con.sql(f"DESCRIBE SELECT * FROM {rel}").fetchall()
        return "\n".join(f"  - `{c[0]}` ({c[1]})" for c in cols)
    except Exception as e:  # noqa: BLE001
        return f"  - could not read: {e}"


def section(con, title: str, files: list[Path], delim=None) -> list[str]:
    out = [f"## {title}", "", f"{len(files)} files", ""]
    for f in files:
        out.append(f"### `{f.name}` ({f.stat().st_size / 1e9:.2f} GB)")
        if f.suffix.lower() in TABULAR:
            out.append(describe(con, f, delim))
        out.append("")
    return out


def main():
    con = duckdb.connect()
    infousa = sorted(paths.INFOUSA_RAW.glob(paths.INFOUSA_GLOB))
    flood = sorted(p for p in paths.FLOOD_EXPOSURE.rglob("*") if p.is_file())
    lines = ["# Data inventory (schema only, no values)", ""]
    lines += section(con, f"infoUSA ({paths.INFOUSA_GLOB})", infousa, paths.INFOUSA_DELIM)
    lines += section(con, "flood_exposure", flood)
    out = paths.LOG_DIR / "data_inventory.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
