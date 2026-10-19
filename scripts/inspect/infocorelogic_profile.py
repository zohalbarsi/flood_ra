"""Profile the InfoCorelogic_v2 folder (corelogic_raw in config/paths.yaml):
an earlier project's address crosswalk between infoUSA and CoreLogic.

Not a pipeline step (run_all.py does not run it). Run it on the server:
    python scripts/inspect/infocorelogic_profile.py [folder]
(default: corelogic_raw). It writes output/logs/profile_<folder name>.md,
which holds no record values:
1. Where the full CoreLogic property data (values, dwelling characteristics)
   are: the folders that the old project's code reads, and any folder under
   the home directory named like CoreLogic, with file names, sizes and
   column names.
2. For the study states: how many of our infoUSA family records the
   crosswalk links to a CoreLogic parcel, by year, plus counts by match code,
   one-to-many links and CoreLogic years.
3. The old project's match statistics (stats/match.csv).
4. The old project's code: the file paths and CoreLogic column names written
   in its .py files, and its lines about the match codes.
It also copies the study states' crosswalk files to derived/corelogic/ as
parquet, and the old code's full comments to code_notes_private.md, in
derived/corelogic/<folder name>/ (stays on the server).
"""
from __future__ import annotations

import ast
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import db, geo, paths  # noqa: E402
from flood_ra.inventory import section  # noqa: E402
from flood_ra.report import mask, pct, table  # noqa: E402

OUT = paths.DERIVED / "corelogic"
DATA_EXT = re.compile(r"\.(csv|gz|parquet|dta|txt|zip|feather|pkl|pickle|sas7bdat|h5)\b", re.I)
COLUMN = re.compile(r"[A-Z0-9][A-Z0-9 _\-/&#%.()]{2,60}")
ADDRESS = re.compile(r"^\d+\s+[A-Z]")  # never print something shaped like a street address


def first_line(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e).splitlines()[0][:200]}" if str(e) else type(e).__name__


# ---------------------------------------------------------------- 1. old code
def strings(src: str) -> list[str]:
    """String literals of a Python file; f-strings with {} for their fields."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return re.findall(r"""['"]([^'"\n]{2,300})['"]""", src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append("".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values))
    return out


def is_path(s: str) -> bool:
    s = s.strip()
    if not s or "\n" in s or len(s) > 300 or s.startswith(("http", "%", "<")):
        return False
    return s.startswith(("/", "~")) or ("/" in s and " " not in s) or bool(DATA_EXT.search(s))


COLUMN_WORDS = re.compile(
    r"\b(CODE|KEY|VALUE|YEAR|AMOUNT|DATE|NUMBER|AREA|FEET|SQUARE|SQ|BUILT|LAND|TAX|SALE|MORTGAGE|"
    r"PRICE|BEDROOMS?|BATH\w*|STOR\w+|UNITS?|ADDRESS|ZIP|FIPS|LATITUDE|LONGITUDE|INDICATOR|TYPE|"
    r"ASSESSED|MARKET|APPRAISED|IMPROVEMENT|LOT|ACRES|CONSTRUCTION|CONDITION|QUALITY|ROOMS?|GARAGE|"
    r"POOL|HEATING|AIR|FIREPLACE|BASEMENT|ROOF|FOUNDATION|STYLE|EFFECTIVE|TOTAL|CALCULATED|SITUS|"
    r"PARCEL|LEGAL|APN|EDITION|RECORDING|DOCUMENT|LOAN|RATE|BUILDING|LIVING|GROSS|ADJUSTED|"
    r"OCCUPANCY|INDICATORS?|COUNT|FLAG|DESCRIPTION|FRONT|DEPTH|ZONING|HISTORIC)\b")
QUOTED = re.compile(r"""(['"])(.*?)\1""")


def is_column(s: str) -> bool:
    """An upper-case literal that reads like a property-data column name."""
    s = s.strip()
    return (COLUMN.fullmatch(s) is not None and not re.search(r"\d", s)
            and COLUMN_WORDS.search(s) is not None)


def redact(line: str) -> str:
    """A code line safe to publish: comment dropped, quoted text kept only if it
    is 'match', an identifier or a column-like name, digit runs of 3+ as 999."""
    code = line.split("#", 1)[0].rstrip()
    def keep(m):
        t = m.group(2)
        ok = t == "match" or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,40}", t) or is_column(t)
        return m.group(1) + (t if ok else "...") + m.group(1)
    return re.sub(r"\d{3,}", "999", QUOTED.sub(keep, code))


MATCH_SET = re.compile(r"""\[\s*['"]match['"]\s*\]\s*=[^=]|\bmatch\s*=\s*\d""")


def code_notes(root: Path, private: Path) -> tuple[list[str], list[str]]:
    """Report lines about the old scripts (safe to publish), and the absolute
    paths they name. The full comment and 'match' lines go to `private`, a
    file under derived/ that stays on the server."""
    scripts = sorted(p for p in root.rglob("*.py") if ".ipynb_checkpoints" not in p.parts)
    lines = ["## 4. The old project's code", "",
             f"{len(scripts)} Python files (Jupyter checkpoints skipped). For each: the file paths "
             "and the column-like upper-case names written in it, and in scripts about merging or "
             "matching, the lines that set a match code with 3 lines before each (comments dropped, "
             "other quoted text shown as ..., digit runs as 999). The full comments and lines "
             f"mentioning `match` are in `{private}` on the server only.", ""]
    found_paths: list[str] = []
    full = [f"# Comments and 'match' lines of the old scripts in {root} (server only, do not commit)", ""]
    for p in scripts:
        rel = p.relative_to(root)
        try:
            src = p.read_text(errors="replace")
            lits = strings(src)
        except (OSError, ValueError, RecursionError) as e:
            lines += [f"### `{rel}`", "", f"unreadable: {first_line(e)}", ""]
            continue
        path_lits = sorted({s.strip() for s in lits if is_path(s)})
        cols = sorted({s.strip() for s in lits if is_column(s)})
        found_paths += [s for s in path_lits if s.startswith(("/", "~"))]
        lines += [f"### `{rel}` ({len(src.splitlines())} lines)", ""]
        if path_lits:
            lines += ["paths:", ""] + [f"- `{re.sub(r'[0-9]{5,}', '99999', s)}`" for s in path_lits[:80]] + [""]
        if cols:
            lines += ["column-like names:", "", "`" + "`, `".join(cols[:300]) + "`", ""]
        if re.search("merge|match", p.name, re.I):
            src_lines = src.splitlines()
            full += [f"## {rel}", "", "```"] + [
                f"{i:5d}  {ln.rstrip()}" for i, ln in enumerate(src_lines, 1)
                if "match" in ln.lower() or ln.strip().startswith("#")] + ["```", ""]
            sets = [i for i, ln in enumerate(src_lines) if MATCH_SET.search(ln.split("#", 1)[0])]
            shown = sorted({j for i in sets for j in range(max(0, i - 3), i + 1)})
            if shown:
                lines += ["```"] + [f"{j + 1:5d}  {redact(src_lines[j])[:160]}" for j in shown[:240]] + ["```", ""]
    private.write_text("\n".join(full))
    return lines, found_paths


# ------------------------------------------------- 2. folders the code points to
def existing_dir(s: str) -> Path | None:
    """The folder a path string names (cut at its first {}), or its parent if
    that is all that exists; None otherwise (no climbing to broad folders)."""
    p = Path(os.path.expanduser(s.split("{", 1)[0]))
    for q in (p, p.parent):
        if q.exists():
            return q
    return None


def listing(con, title: str, d: Path, cap: int = 20_000) -> list[str]:
    n = 0
    for _, _, files in os.walk(d):
        n += len(files)
        if n > cap:
            break
    if n <= cap:
        return section(con, title, d, max_files=40)
    entries = sorted(d.iterdir())
    out = [f"## {title}", "", f"`{d}`: more than {cap:,} files; top level only ({len(entries)} entries):", ""]
    for e in entries[:150]:
        try:
            tag = "/" if e.is_dir() else f" ({e.stat().st_size / 1e9:.2f} GB)"
        except OSError:
            tag = " (broken link)" if e.is_symlink() else " (unreadable)"
        out.append(f"- `{e.name}`" + tag)
    return out + [""]


def named_like_corelogic(roots: list[Path], skip: set[Path], max_depth: int = 6,
                         max_dirs: int = 100_000) -> tuple[list[Path], list[str]]:
    """Folders named like CoreLogic under each root (each root has its own
    budget of folders visited); also returns notes on searches cut short."""
    hits, notes = [], []
    for root in roots:
        base, seen = len(root.parts), 0
        for d, subdirs, files in os.walk(root, onerror=lambda e: None):
            seen += 1
            depth = len(Path(d).parts) - base
            subdirs[:] = [s for s in subdirs if not s.startswith(".") and depth < max_depth
                          and s not in {".venv", "__pycache__", "miniconda3", "anaconda3"}
                          and Path(d, s).resolve() not in skip]
            if re.search("corelogic|histproperty|core_logic", Path(d).name, re.I):
                hits.append(Path(d))
                subdirs[:] = []
            elif any(re.search("corelogic|histproperty", f, re.I) for f in files):
                hits.append(Path(d))
            if seen >= max_dirs:
                notes.append(f"search in `{root}` stopped after {seen:,} folders")
                break
    return hits, notes


def folders(con, root: Path, code_paths: list[str]) -> list[str]:
    home = Path.home().resolve()
    candidates = {}
    for s in code_paths:
        d = existing_dir(s)
        if d is None:
            continue
        d = d.resolve()
        if d.is_file():
            d = d.parent
        # skip the crosswalk folder itself and folders too broad to list
        if (d == root or root in d.parents or d in root.parents or d in home.parents or d == home
                or d.parent == home or len(d.parts) < 4):
            continue
        candidates[d] = s
    roots = [home] + [Path(r) for r in ("/project", "/data", "/scratch") if Path(r).is_dir()]
    hits, cut = named_like_corelogic(roots, {paths.REPO_ROOT.resolve(), paths.DERIVED.resolve()})
    hits = [h.resolve() for h in hits]
    hits = [h for h in hits if h != root and root not in h.parents]
    lines = ["## 1. Folders the old code reads, and folders named like CoreLogic", "",
             f"Paths in the code that exist on this server ({len(candidates)} folders). Folders named "
             f"like CoreLogic or HistProperty under {', '.join(f'`{r}`' for r in roots)} (6 levels "
             f"deep; the crosswalk folder, this repo and derived/ excluded): {len(hits)}."
             + ("" if not cut else " Note: " + "; ".join(cut) + "."), ""]
    lines += [f"- `{h}`" for h in hits[:50]] + [""]
    todo = list(dict.fromkeys(list(candidates) + hits))
    for d in todo[:12]:
        try:
            lines += listing(con, f"folder `{d}`", d)
        except Exception as e:  # noqa: BLE001
            lines += [f"## folder `{d}`", "", f"could not list: {first_line(e)}", ""]
    if len(todo) > 12:
        lines += [f"... {len(todo) - 12} more folders not listed", ""]
    return lines


# --------------------------------------------------------- 3. crosswalk coverage
def to_parquet(con, src: Path, name: str) -> Path | None:
    """Copy one crosswalk file to derived/corelogic/<name>.parquet (all text)."""
    out = OUT / f"{name}.parquet"
    if out.exists() and out.stat().st_mtime > src.stat().st_mtime:
        return out
    tmp = out.with_suffix(".parquet.tmp")
    con.sql(f"COPY (SELECT * FROM read_csv('{src.as_posix()}', all_varchar=true, header=true)) "
            f"TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    tmp.replace(out)
    return out


def coverage(con, root: Path, state: str) -> list[str]:
    files = {
        "info_xwalk": root / "input" / f"{state}_InfoUSA" / f"{state}_addid_all.csv.gz",
        "cl_xwalk": root / "input" / f"{state}_cl" / f"{state}_Historical" / f"{state}_addid_all.csv.gz",
        "cl_hist": root / "input" / f"{state}_cl" / f"{state}_Historical" / f"{state}_Historical.csv.gz",
        "merge": root / "output" / f"{state}_merge" / f"{state}_addid_merge_all.csv.gz",
    }
    lines = [f"### {state}", ""]
    pq = {}
    for name, f in files.items():
        if not f.exists():
            lines += [f"- `{f.relative_to(root)}` not found", ""]
            continue
        t0 = time.time()
        try:
            pq[name] = f"read_parquet('{to_parquet(con, f, f'{state}_{name}').as_posix()}')"
            print(f"  {state} {name}: parquet ready ({time.time() - t0:.0f}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            lines += [f"- `{f.relative_to(root)}` could not be read: {first_line(e)}", ""]
    if "info_xwalk" not in pq or "merge" not in pq:
        return lines + ["Coverage needs the infoUSA crosswalk and the merge file.", ""]

    con.sql(f"""CREATE OR REPLACE TABLE xw AS
                SELECT TRY_CAST(year AS INT) AS year, TRY_CAST(FAMILYID AS BIGINT) AS fid,
                       TRY_CAST(info_addid AS BIGINT) AS aid FROM {pq['info_xwalk']}""")
    con.sql(f"""CREATE OR REPLACE TABLE mg AS
                SELECT TRY_CAST(info_addid AS BIGINT) AS aid, TRY_CAST(cl_addid AS BIGINT) AS cid,
                       "COMPOSITE PROPERTY LINKAGE KEY" AS lk, TRY_CAST(match AS DOUBLE) AS match,
                       "LAND USE CODE" AS land_use, "PROPERTY INDICATOR CODE" AS prop_ind
                FROM {pq['merge']}""")
    con.sql("CREATE OR REPLACE TABLE linked AS SELECT DISTINCT aid FROM mg")

    # (a) the crosswalk itself, by year
    x = con.sql("""SELECT year, count(*) AS rows, count(DISTINCT fid) AS families,
                          count(DISTINCT aid) AS addresses,
                          count(DISTINCT aid) FILTER (WHERE aid IN (SELECT aid FROM linked)) AS linked
                   FROM xw GROUP BY year ORDER BY year""").df()
    rows = [[y if pd.notna(y) else "(bad)", f"{r:,}", f"{fa:,}", f"{a:,}", pct(l / a if a else None)]
            for y, r, fa, a, l in x.itertuples(index=False)]
    lines += [f"**{files['info_xwalk'].name}** (infoUSA side) by `year`: rows, distinct FAMILYIDs, "
              "distinct info_addid, and the share of those addresses that the merge file links to "
              "a CoreLogic parcel.", "",
              *table(pd.DataFrame(rows, columns=["year", "rows", "FAMILYIDs", "addresses",
                                                 "address linked"]))]

    # (b) our family records found in the crosswalk, by year
    ours = []
    for year, f in paths.chosen_files().items():
        r = con.sql(f"""
            WITH o AS (SELECT DISTINCT TRY_CAST(trim(FAMILYID) AS BIGINT) AS fid,
                              trim(PRIMARY_FAMILY_IND) = '1' AS prim
                       FROM read_parquet('{f.as_posix()}') WHERE upper(trim(STATE)) = '{state}'),
                 x AS (SELECT fid, bool_or(aid IN (SELECT aid FROM linked)) AS link
                       FROM xw WHERE year = {year} GROUP BY fid)
            SELECT count(*), count(*) FILTER (WHERE prim),
                   count(x.fid), count(x.fid) FILTER (WHERE prim),
                   count(*) FILTER (WHERE prim AND x.link),
                   (SELECT count(*) FROM x)
            FROM o LEFT JOIN x ON x.fid = o.fid
        """).fetchone()
        n, prim, found, found_p, link_p, nx = r
        ours.append([year, f"{n:,}", pct(found / n if n else None), f"{prim:,}",
                     pct(found_p / prim if prim else None), pct(link_p / prim if prim else None),
                     f"{nx:,}"])
    lines += ["Our family records (step 01 files, this state) whose FAMILYID is in the crosswalk "
              "for the same year; for primary families, also the share whose address is linked to "
              "a CoreLogic parcel. last column: FAMILYIDs in the crosswalk for that year.", "",
              *table(pd.DataFrame(ours, columns=["year", "family records", "records in crosswalk",
                                                 "primary families", "primary in crosswalk",
                                                 "primary linked to parcel", "crosswalk FAMILYIDs"]))]

    # (c) the merge file: match codes and one-to-many links
    m = con.sql("SELECT count(*), count(DISTINCT aid), count(DISTINCT cid), count(DISTINCT lk) FROM mg").fetchone()
    lines += [f"**{files['merge'].name}**: {m[0]:,} rows; {m[1]:,} infoUSA addresses, {m[2]:,} CoreLogic "
              f"addresses, {m[3]:,} parcels (linkage keys).", ""]
    mc = con.sql("""SELECT match, count(*), count(DISTINCT aid) FROM mg GROUP BY match ORDER BY match""").df()
    mc.columns = ["match code", "rows", "infoUSA addresses"]
    mc["share of rows"] = (mc["rows"] / mc["rows"].sum()).map(pct)
    lines += ["By match code (meaning: see the merge script in section 4):", "", *table(mc)]
    for label, key, other in (("parcels per infoUSA address", "aid", "lk"),
                              ("infoUSA addresses per parcel", "lk", "aid")):
        d = con.sql(f"""SELECT CASE WHEN k = 1 THEN '1' WHEN k = 2 THEN '2' WHEN k <= 5 THEN '3-5'
                                    WHEN k <= 20 THEN '6-20' ELSE '21+' END AS n, count(*) AS c
                        FROM (SELECT {key}, count(DISTINCT {other}) AS k FROM mg GROUP BY {key})
                        GROUP BY n ORDER BY min(k)""").df()
        d["share"] = (d["c"] / d["c"].sum()).map(pct)
        d.columns = [label, "count", "share"]
        lines += table(d)
    for col, label in (("land_use", "LAND USE CODE"), ("prop_ind", "PROPERTY INDICATOR CODE")):
        d = con.sql(f"SELECT {col}, count(*) FROM mg GROUP BY 1 ORDER BY 2 DESC LIMIT 12").df()
        d.columns = [label, "rows"]
        d[label] = d[label].map(mask)
        d["share"] = (d["rows"] / m[0]).map(pct)
        lines += [f"Merge rows by {label} (top 12):", "", *table(d)]

    # (d) CoreLogic years
    if "cl_hist" in pq:
        h = con.sql(f"""
            SELECT TRY_CAST(YEAR AS INT) AS y, count(*), count(DISTINCT "COMPOSITE PROPERTY LINKAGE KEY"),
                   count(DISTINCT "COMPOSITE PROPERTY LINKAGE KEY")
                       FILTER (WHERE "COMPOSITE PROPERTY LINKAGE KEY" IN (SELECT lk FROM mg))
            FROM {pq['cl_hist']} GROUP BY y ORDER BY y""").df()
        h.columns = ["YEAR", "rows", "parcels", "parcels in merge"]
        lines += [f"**{files['cl_hist'].name}** (CoreLogic history extract) by `YEAR`:", "", *table(h)]
        b = con.sql(f"SELECT base_year, count(*) FROM {pq['cl_hist']} GROUP BY 1 ORDER BY 2 DESC LIMIT 10").df()
        b.columns = ["base_year", "rows"]
        b["base_year"] = b["base_year"].map(mask)
        lines += ["`base_year` (top 10):", "", *table(b)]
    return lines


def match_stats(con, root: Path) -> list[str]:
    f = root / "stats" / "match.csv"
    if not f.exists():
        return []
    d = con.sql(f"SELECT * FROM read_csv('{f.as_posix()}', header=true)").df()
    return ["## 3. stats/match.csv (the old project's match statistics, all states)", "",
            *table(d.round(3))]


def main() -> None:
    folder = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else paths.CORELOGIC_RAW
    if folder is None:
        sys.exit("give the folder, or set corelogic_raw in config/paths.yaml")
    paths.require(folder)
    root = folder.resolve()
    global OUT
    OUT = paths.DERIVED / "corelogic" / root.name
    OUT.mkdir(parents=True, exist_ok=True)
    report = paths.LOG_DIR / f"profile_{root.name}.md"
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    t0 = time.time()
    lines = [f"# {root.name} profile (counts, schemas and code notes; no record values)", "",
             f"Folder `{root}`.", ""]

    def save() -> None:
        report.write_text("\n".join(lines + [f"_{(time.time() - t0) / 60:.1f} minutes so far_"]))

    try:
        notes, code_paths = code_notes(root, OUT / "code_notes_private.md")
    except Exception as e:  # noqa: BLE001
        notes, code_paths = ["## 4. The old project's code", "", f"failed: {first_line(e)}", ""], []
    print("1. folders", flush=True)
    try:
        lines += folders(con, root, code_paths)
    except Exception as e:  # noqa: BLE001
        lines += ["## 1. Folders", "", f"failed: {first_line(e)}", ""]
    save()
    print("2. crosswalk coverage", flush=True)
    lines += ["## 2. Crosswalk coverage, study states", ""]
    for state in geo.study_states():
        try:
            lines += coverage(con, root, state)
        except Exception as e:  # noqa: BLE001
            lines += [f"### {state}", "", f"failed: {first_line(e)}", ""]
        save()
    try:
        lines += match_stats(con, root)
    except Exception as e:  # noqa: BLE001
        lines += ["## 3. stats/match.csv", "", f"could not read: {first_line(e)}", ""]
    lines += notes
    save()
    print(f"wrote {report}")


if __name__ == "__main__":
    main()
