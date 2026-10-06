"""Step 0: inventory the raw data on the server WITHOUT copying any of it.

Writes output/logs/data_inventory.md: every file in the infoUSA and
flood_exposure folders with its size, plus the delimiter, header and column
names/types of each tabular file. The report holds no data values, so it is
safe to commit and share; it is how code written elsewhere learns the schema
of data that never leaves the server.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths, settings  # noqa: E402

TEXT = {".csv", ".txt", ".tsv", ".dat", ".gz"}


def describe(con, f: Path) -> list[str]:
    """Column names/types of one file; nothing for non-tabular files."""
    suffix = f.suffix.lower()
    try:
        if suffix == ".dta":
            import pandas as pd
            with pd.read_stata(f, iterator=True) as reader:
                return [f"  - `{v}`: {label}" for v, label in reader.variable_labels().items()]
        if suffix == ".parquet":
            cols = con.sql(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()
            return [f"  - `{c[0]}` ({c[1]})" for c in cols]
        if suffix in TEXT:
            delim, header, cols = con.sql(
                "SELECT Delimiter, HasHeader, Columns "
                f"FROM sniff_csv('{f.as_posix()}', sample_size=20000)"
            ).fetchone()
            out = [f"  delimiter {delim!r}, header {header}, {len(cols)} columns", ""]
            return out + [f"  - `{c['name']}` ({c['type']})" for c in cols]
    except Exception as e:  # noqa: BLE001
        # first line only: later lines of a CSV error can quote a data row
        return [f"  - could not read: {type(e).__name__}: {str(e).splitlines()[0][:150]}"]
    return []


def section(con, title: str, root: Path, glob: str | None = None) -> list[str]:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    sizes = {p: p.stat().st_size / 1e9 for p in files}
    exts = Counter(p.suffix.lower() or "(none)" for p in files)
    out = [f"## {title}", "", f"`{root}`: {len(files)} files, {sum(sizes.values()):.1f} GB", "",
           "by extension: " + ", ".join(f"{e} ({n})" for e, n in exts.most_common()), ""]
    if glob is not None:
        n = sum(1 for p in root.glob(glob) if p.is_file())
        out += [f"**{n} match infousa_glob `{glob}`** (the files step 01 converts)", ""]
    for f in files:
        out.append(f"### `{f.relative_to(root)}` ({sizes[f]:.2f} GB)")
        out += describe(con, f)
        out.append("")
    return out


def main():
    paths.require(paths.INFOUSA_RAW, paths.FLOOD_EXPOSURE)
    con = duckdb.connect()
    lines = ["# Data inventory (schema only, no values)", ""]
    lines += section(con, "infoUSA", paths.INFOUSA_RAW, settings.INFOUSA_GLOB)
    lines += section(con, "flood_exposure", paths.FLOOD_EXPOSURE)
    out = paths.LOG_DIR / "data_inventory.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
