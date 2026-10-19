"""Profile the InfoCorelogic_v2 folder (corelogic_raw in config/paths.yaml):
an earlier project's address crosswalk between infoUSA and CoreLogic.

Not a pipeline step (run_all.py does not run it). Run it once on the server:
    python scripts/inspect/infocorelogic_profile.py
It writes output/logs/infocorelogic_profile.md, which holds no record values:
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
parquet (licensed data, stays on the server) for the merge that will follow.
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

REPORT = paths.LOG_DIR / "infocorelogic_profile.md"
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


def is_column(s: str) -> bool:
    return (" " in s.strip() and COLUMN.fullmatch(s.strip()) is not None
            and not ADDRESS.match(s.strip()))


def code_notes(root: Path) -> tuple[list[str], list[str]]:
    """Report lines about the old scripts, and the absolute paths they name."""
    scripts = sorted(p for p in root.rglob("*.py") if ".ipynb_checkpoints" not in p.parts)
    lines = ["## 4. The old project's code", "",
             f"{len(scripts)} Python files (Jupyter checkpoints skipped). For each: the file paths "
             "and the upper-case column names written in it; for scripts about merging or "
             "matching, also its comments and the lines that mention `match`.", ""]
    found_paths: list[str] = []
    for p in scripts:
        src = p.read_text(errors="replace")
        lits = strings(src)
        path_lits = sorted({s.strip() for s in lits if is_path(s)})
        cols = sorted({s.strip() for s in lits if is_column(s)})
        found_paths += [s for s in path_lits if s.startswith(("/", "~"))]
        lines += [f"### `{p.relative_to(root)}` ({len(src.splitlines())} lines)", ""]
        if path_lits:
            lines += ["paths:", ""] + [f"- `{s}`" for s in path_lits[:80]] + [""]
        if cols:
            lines += ["upper-case names (CoreLogic columns, mostly):", "",
                      "`" + "`, `".join(cols[:300]) + "`", ""]
        if re.search("merge|match", p.name, re.I):
            keep = [(i, ln.rstrip()) for i, ln in enumerate(src.splitlines(), 1)
                    if ("match" in ln.lower() or ln.strip().startswith("#")) and not ADDRESS.search(ln.strip())]
            if keep:
                lines += ["```"] + [f"{i:5d}  {ln[:160]}" for i, ln in keep[:200]] + ["```", ""]
                if len(keep) > 200:
                    lines += [f"... {len(keep) - 200} more lines", ""]
    return lines, found_paths


# ------------------------------------------------- 2. folders the code points to
def existing_dir(s: str) -> Path | None:
    """Deepest existing folder on the way to a path string (cut at its first {})."""
    p = Path(os.path.expanduser(s.split("{", 1)[0]))
    while not p.exists() and p != p.parent:
        p = p.parent
    return p if p.exists() else None


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
        out.append(f"- `{e.name}`" + ("/" if e.is_dir() else f" ({e.stat().st_size / 1e9:.2f} GB)"))
    return out + [""]


def named_like_corelogic(roots: list[Path], max_depth: int = 6, max_dirs: int = 200_000) -> list[Path]:
    hits, seen = [], 0
    for root in roots:
        base = len(root.parts)
        for d, subdirs, files in os.walk(root):
            seen += 1
            depth = len(Path(d).parts) - base
            subdirs[:] = [s for s in subdirs if not s.startswith(".") and s not in {".venv", "__pycache__"}
                          and depth < max_depth]
            if re.search("corelogic|histproperty|core_logic", Path(d).name, re.I):
                hits.append(Path(d))
                subdirs[:] = []
            elif any(re.search("corelogic|histproperty", f, re.I) for f in files):
                hits.append(Path(d))
            if seen > max_dirs:
                return hits
    return hits


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
        if d == root or root in d.parents or d in home.parents or d == home or len(d.parts) < 3:
            continue
        candidates[d] = s
    roots = [home] + [Path(r) for r in ("/project", "/data", "/scratch") if Path(r).is_dir()]
    hits = [h.resolve() for h in named_like_corelogic(roots)]
    hits = [h for h in hits if h != root and root not in h.parents]
    lines = ["## 1. Folders the old code reads, and folders named like CoreLogic", "",
             f"Paths in the code that exist on this server ({len(candidates)} folders). Folders named "
             f"like CoreLogic or HistProperty under {', '.join(f'`{r}`' for r in roots)} (6 levels "
             f"deep; the crosswalk folder excluded): {len(hits)}.", ""]
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
    if paths.CORELOGIC_RAW is None:
        sys.exit("set corelogic_raw in config/paths.yaml to the InfoCorelogic_v2 folder")
    paths.require(paths.CORELOGIC_RAW)
    root = paths.CORELOGIC_RAW.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    t0 = time.time()
    lines = ["# InfoCorelogic_v2 profile (counts, schemas and code notes; no record values)", ""]

    notes, code_paths = code_notes(root)
    print("1. folders", flush=True)
    try:
        lines += folders(con, root, code_paths)
    except Exception as e:  # noqa: BLE001
        lines += ["## 1. Folders", "", f"failed: {first_line(e)}", ""]
    print("2. crosswalk coverage", flush=True)
    lines += ["## 2. Crosswalk coverage, study states", ""]
    for state in geo.study_states():
        try:
            lines += coverage(con, root, state)
        except Exception as e:  # noqa: BLE001
            lines += [f"### {state}", "", f"failed: {first_line(e)}", ""]
    try:
        lines += match_stats(con, root)
    except Exception as e:  # noqa: BLE001
        lines += ["## 3. stats/match.csv", "", f"could not read: {first_line(e)}", ""]
    lines += notes  # the code notes go last: they are long
    lines.insert(2, f"Folder `{root}`. {(time.time() - t0) / 60:.1f} minutes.\n")
    REPORT.write_text("\n".join(lines))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
