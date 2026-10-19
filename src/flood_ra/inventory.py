"""Schema-only descriptions of data files: names, sizes, column names and
types, never values, so the output is safe to commit. A CSV header the sniffer
cannot confirm (all columns text) could be a data row, so its names are
masked unless they look like identifiers (see safe_name)."""
from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

TEXT = {".csv", ".txt", ".tsv", ".dat", ".gz"}


_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)+")


def safe_name(name: str) -> str:
    """A column name from an unconfirmed header: as is if it looks like an
    identifier with an underscore (no 5+ digit runs), else its pattern."""
    if _IDENT.fullmatch(name) and not re.search(r"\d{5}", name):
        return name
    return re.sub("[A-Za-z]", "A", re.sub(r"\d", "9", name))


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
            # A header is certain only if some column has a non-text type (the first
            # row then failed to parse as data). Otherwise the "names" may be a data
            # row, so only identifier-like names with an underscore are shown as
            # they are; the rest are shown as patterns (A = letter, 9 = digit).
            confirmed = header and any(c["type"] != "VARCHAR" for c in cols)
            note = "" if confirmed or not header else " (header not confirmed: all text)"
            out = [f"  delimiter {delim!r}, header {header}{note}, {len(cols)} columns", ""]
            return out + [f"  - `{c['name'] if confirmed or not header else safe_name(c['name'])}` ({c['type']})"
                          for c in cols]
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


# State postal codes (plus DC, PR) as they appear in per-state file names
STATE_CODES = ("AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|"
               "NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|PR")
_STATE = re.compile(rf"(?<![A-Za-z])({STATE_CODES})(?![A-Za-z])")


def pattern(rel: str) -> str:
    """File path with state codes as {ST} and digit runs as #."""
    return re.sub(r"\d+", "#", _STATE.sub("{ST}", rel))


def compact_section(con, title: str, root: Path, prefer: tuple[str, ...] = (),
                    list_max: int = 12) -> list[str]:
    """Like section(), but files are grouped by name pattern (state codes as
    {ST}, digits as #) and each distinct column layout in a group is shown
    once, with the files that share it. Every tabular file is still read.
    Files of the `prefer` states are listed first."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    sizes = {p: p.stat().st_size / 1e9 for p in files}
    exts = Counter(p.suffix.lower() or "(none)" for p in files)
    groups: dict[str, list[Path]] = {}
    for f in files:
        groups.setdefault(pattern(str(f.relative_to(root))), []).append(f)
    out = [f"## {title}", "", f"`{root}`: {len(files)} files, {sum(sizes.values()):.1f} GB, "
           f"{len(groups)} name patterns", "",
           "by extension: " + ", ".join(f"{e} ({n})" for e, n in exts.most_common()), "",
           "Files grouped by name pattern ({ST} = a state code, # = digits). Each distinct "
           "column layout in a group is listed once, with the files that have it.", ""]

    def names(ms: list[Path]) -> str:
        ms = sorted(ms, key=lambda m: not any(c in prefer for c in _STATE.findall(str(m.relative_to(root)))))
        shown = ", ".join(f"`{m.relative_to(root)}` ({sizes[m]:.2f} GB)" for m in ms[:list_max])
        return shown + (f", ... and {len(ms) - list_max} more" if len(ms) > list_max else "")

    for pat, members in groups.items():
        states = sorted({m.group(1) for f in members for m in _STATE.finditer(str(f.relative_to(root)))})
        out.append(f"### `{pat}` ({len(members)} files, {sum(sizes[m] for m in members):.2f} GB)")
        if states:
            out.append(f"states ({len(states)}): {' '.join(states)}")
        out.append("")
        layouts: dict[tuple, list[Path]] = {}
        for f in members:
            layouts.setdefault(tuple(describe(con, f)), []).append(f)
        for layout, ms in layouts.items():
            out += [f"{len(ms)} file(s): {names(ms)}", ""]
            out += list(layout) + ([""] if layout else [])
    return out
