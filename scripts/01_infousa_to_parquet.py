"""Step 1: convert each yearly infoUSA Consumer file to Parquet, once.

Reads the raw .csv.gz in place (never modified), keeps households whose
address state is a study state, drops the columns listed in settings.yaml
(names), and writes derived/infousa_parquet/infousa_<year>[_<version>].parquet.
Every column stays text so codes keep their leading zeros. Several files run
at once (parallel_files in paths.yaml); finished files are skipped on re-runs
(--overwrite redoes them). Rows the CSV reader rejects are counted by error
type, never stored. Each .gz is also checked with `gzip -t` alongside the
conversion, because DuckDB silently reads a truncated file up to the cut.
One line per file goes to output/logs/infousa_conversion.txt.
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402

LOG = paths.LOG_DIR / "infousa_conversion.txt"
REJECTS_LIMIT = 10_000


def raw_files() -> list[tuple[int, str, Path]]:
    """(year, version, path) per yearly file; version is "main" for the top folder."""
    out = []
    for f in sorted(paths.INFOUSA_RAW.glob(settings.INFOUSA_GLOB)):
        year = settings.year_of(f.name)
        if year is not None:
            version = "main" if f.parent == paths.INFOUSA_RAW else f.parent.name
            out.append((year, version, f))
    dupes = [k for k, n in Counter((y, v) for y, v, _ in out).items() if n > 1]
    if dupes:
        sys.exit(f"several raw files for the same year and version: {dupes}; "
                 "narrow infousa_glob in config/settings.yaml")
    return out


def quote(col: str) -> str:
    return '"' + col.replace('"', '""') + '"'


def convert(year: int, version: str, f: Path, states: list[str]) -> str:
    t0 = time.time()
    out = paths.infousa_parquet(year, version)
    tmp = out.with_suffix(".parquet.tmp")
    check = None
    if f.suffix == ".gz" and shutil.which("gzip"):
        check = subprocess.Popen(["gzip", "-t", str(f)], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, text=True)
    try:
        line = _convert(year, f, states, tmp)
        if check is not None:
            err = check.communicate()[1].strip()
            if check.returncode == 1:  # 2 = warning only, e.g. trailing zeros
                raise RuntimeError(f"gzip integrity check failed: {(err.splitlines() or ["no message"])[0][:200]}")
            line += f"; gzip warning: {(err.splitlines() or ["no message"])[0][:200]}" if check.returncode == 2 else ""
    except BaseException:
        if check is not None and check.poll() is None:
            check.kill()
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(out)  # only a finished, intact file gets the final name
    return f"{year} {version} ({f.name}): {line}; {(time.time() - t0) / 60:.1f} min"


def _convert(year: int, f: Path, states: list[str], tmp: Path) -> str:
    con = db.connect()
    opts = (f"all_varchar=true, header=true, delim='{settings.INFOUSA_DELIM}', "
            f"encoding='{settings.INFOUSA_ENCODING}'")
    cols = [r[0] for r in con.sql(
        f"DESCRIBE SELECT * FROM read_csv('{f.as_posix()}', {opts}, ignore_errors=true)").fetchall()]
    keep = [c for c in cols if not any(fnmatch.fnmatchcase(c, p) for p in settings.DROP_COLUMNS)]
    in_states = ", ".join(f"'{s}'" for s in states)
    con.sql(f"""
        COPY (
            SELECT {year} AS year, {', '.join(map(quote, keep))}, '{f.name}' AS source_file
            FROM read_csv('{f.as_posix()}', {opts}, store_rejects=true, rejects_limit={REJECTS_LIMIT})
            WHERE upper(trim("STATE")) IN ({in_states})
        ) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    # error types and counts only: the rejects table also holds the raw lines
    rejects = con.sql("SELECT error_type, count(*) FROM reject_errors GROUP BY 1 ORDER BY 1").fetchall()
    by_state = con.sql(f"SELECT upper(trim(STATE)), count(*) FROM read_parquet('{tmp.as_posix()}') "
                       "GROUP BY 1 ORDER BY 1").fetchall()
    kept = sum(n for _, n in by_state)
    rej = "; ".join(f"{t} {n:,}" for t, n in rejects) or "none"
    if sum(n for _, n in rejects) >= REJECTS_LIMIT:
        rej += f" (capped at {REJECTS_LIMIT:,})"
    return (f"{kept:,} households kept ({', '.join(f'{s} {n:,}' for s, n in by_state)}); "
            f"{len(keep)} of {len(cols)} columns; rejected rows: {rej}")


def main(overwrite: bool = False) -> None:
    paths.require(paths.INFOUSA_RAW, paths.FLOOD_EXPOSURE)
    states = geo.study_states()
    files = raw_files()
    if not files:
        sys.exit(f"no files match {settings.INFOUSA_GLOB} in {paths.INFOUSA_RAW}")
    todo = [x for x in files if overwrite or not paths.infousa_parquet(x[0], x[1]).exists()]
    print(f"study states: {', '.join(states)}")
    for x in files:
        print(f"  {x[0]} {x[1]:5} {x[2].relative_to(paths.INFOUSA_RAW)}"
              f"  [{'convert' if x in todo else 'done, skip'}]")
    print(f"converting {len(todo)} files, {paths.PARALLEL} at a time", flush=True)
    failed = 0
    with ThreadPoolExecutor(max_workers=paths.PARALLEL) as pool:
        jobs = {pool.submit(convert, y, v, f, states): f for y, v, f in todo}
        for job in as_completed(jobs):
            try:
                line = job.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                # first line only: later lines of a CSV error can quote a data row
                line = f"FAILED {jobs[job].name}: {type(e).__name__}: {str(e).splitlines()[0][:200]}"
            print(line, flush=True)
            with open(LOG, "a") as log:
                log.write(f"{datetime.now():%Y-%m-%d %H:%M}  {line}\n")
    if failed:
        sys.exit(f"{failed} file(s) failed; see {LOG}")


if __name__ == "__main__":
    main(overwrite="--overwrite" in sys.argv)
