"""Schema-only descriptions of data files: names, sizes, column names and
types, never values, so the output is safe to commit."""
from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path

TEXT = {".csv", ".txt", ".tsv", ".dat", ".gz"}


def describe(con, f: Path) -> list[str]:
    """Column names/types of one file; nothing for non-tabular files."""
    suffix = f.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                members = [m for m in z.infolist() if not m.is_dir()]
            return ([f"  {len(members)} files inside:"]
                    + [f"  - `{m.filename}` ({m.file_size / 1e9:.2f} GB unzipped)" for m in members[:50]]
                    + ([f"  - ... and {len(members) - 50} more"] if len(members) > 50 else []))
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


def section(con, title: str, root: Path, glob: str | None = None, max_files: int | None = None) -> list[str]:
    """Markdown listing of every file under root with its schema. With
    max_files, only the first file of each name pattern (digits as #) is
    described, up to max_files of them; the rest are counted."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    sizes = {p: p.stat().st_size / 1e9 for p in files}
    exts = Counter(p.suffix.lower() or "(none)" for p in files)
    out = [f"## {title}", "", f"`{root}`: {len(files)} files, {sum(sizes.values()):.1f} GB", "",
           "by extension: " + ", ".join(f"{e} ({n})" for e, n in exts.most_common()), ""]
    if glob is not None:
        n = sum(1 for p in root.glob(glob) if p.is_file())
        out += [f"**{n} match infousa_glob `{glob}`** (the files step 01 converts)", ""]
    if max_files is not None:
        import re
        groups: dict[str, list[Path]] = {}
        for f in files:
            groups.setdefault(re.sub(r"\d", "#", str(f.relative_to(root))), []).append(f)
        for pattern, members in list(groups.items())[:max_files]:
            f = members[0]
            out.append(f"### `{pattern}` ({len(members)} files, {sum(sizes[m] for m in members):.2f} GB; "
                       f"first: `{f.relative_to(root)}`)")
            out += describe(con, f)
            out.append("")
        if len(groups) > max_files:
            out += [f"... and {len(groups) - max_files} more name patterns", ""]
        return out
    for f in files:
        out.append(f"### `{f.relative_to(root)}` ({sizes[f]:.2f} GB)")
        out += describe(con, f)
        out.append("")
    return out
