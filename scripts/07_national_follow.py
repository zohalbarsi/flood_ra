"""Step 7: find the panel households' records outside the study states.

The panel (step 08) follows every household that is a primary family in a
study state in at least one year up to last_year, in every year it appears
anywhere in the US. The converted files (step 01) hold only the study states,
so this step reads each year's national file once, as step 01 does, and keeps
the records outside the study states that belong to the panel: the same
FAMILYID, or any adult (IndividualID_1-5) ever listed in a panel household.
The adult match lets step 08 follow a household whose FAMILYID changes.

Writes (record level, stays on the server): derived/panel/ids_family.parquet,
derived/panel/ids_person.parquet and derived/panel/national/infousa_<year>.parquet
(the columns in flood_ra.panel.COLUMNS only). Log (counts only):
output/logs/national_follow.txt.

Slow: each national file is read once (about 15 minutes each, parallel_files
at a time). A year already done for the same panel is skipped, so a stopped
run can simply be started again.
"""
from __future__ import annotations

import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import db, geo, panel, paths, settings  # noqa: E402

LOG = paths.LOG_DIR / "national_follow.txt"
REJECTS_LIMIT = 10_000


def quote(col: str) -> str:
    return '"' + col.replace('"', '""') + '"'


def build_ids(files: dict[int, Path], states: list[str], sig: str) -> None:
    """Panel FAMILYIDs (primary family in a study state in some year) and every
    adult listed in their study-state records. Built in slices of IDs so the
    de-duplication fits in memory (no large temporary files)."""
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    src = "read_parquet([" + ", ".join(f"'{f.as_posix()}'" for f in files.values()) + "], union_by_name=true)"
    cols = {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    where = (f"upper(trim(STATE)) IN ({', '.join(repr(s) for s in states)}) "
             "AND nullif(trim(FAMILYID), '') IS NOT NULL")
    parts = panel.DIR / "ids_parts"
    shutil.rmtree(parts, ignore_errors=True)
    parts.mkdir(parents=True)
    try:
        for k in range(panel.SLICES):
            con.sql(f"""COPY (SELECT DISTINCT trim(FAMILYID) AS id FROM {src}
                              WHERE {where} AND trim(PRIMARY_FAMILY_IND) = '1'
                                AND hash(trim(FAMILYID)) % {panel.SLICES} = {k})
                        TO '{(parts / f"family_{k}.parquet").as_posix()}' (FORMAT parquet)""")
        fam = f"(SELECT id FROM read_parquet('{(parts / 'family_*.parquet').as_posix()}'))"
        for k in range(panel.SLICES):
            con.sql(f"""COPY (
                SELECT DISTINCT p AS id FROM (
                    SELECT unnest({panel.persons_list(cols)}) AS p FROM {src}
                    WHERE {where} AND trim(FAMILYID) IN {fam})
                WHERE p IS NOT NULL AND hash(p) % {panel.SLICES} = {k}
            ) TO '{(parts / f"person_{k}.parquet").as_posix()}' (FORMAT parquet)""")
            print(f"  adults: slice {k + 1} of {panel.SLICES}", flush=True)
        # the slices hold disjoint IDs, so joining them needs no de-duplication
        for name, out in (("family", panel.IDS_FAMILY), ("person", panel.IDS_PERSON)):
            tmp = out.with_suffix(".parquet.tmp")
            con.sql(f"COPY (SELECT id FROM read_parquet('{(parts / f'{name}_*.parquet').as_posix()}')) "
                    f"TO '{tmp.as_posix()}' (FORMAT parquet, {panel.metadata(sig)})")
            tmp.replace(out)
    finally:
        shutil.rmtree(parts, ignore_errors=True)


def follow(year: int, raw: Path, states: list[str], sig: str) -> str:
    """Keep one year's records outside the study states that belong to the panel."""
    t0 = time.time()
    out = panel.national_file(year)
    tmp = out.with_suffix(".parquet.tmp")
    con = db.connect()
    opts = (f"all_varchar=true, header=true, delim='{settings.INFOUSA_DELIM}', "
            f"encoding='{settings.INFOUSA_ENCODING}'")
    cols = [r[0] for r in con.sql(
        f"DESCRIBE SELECT * FROM read_csv('{raw.as_posix()}', {opts}, ignore_errors=true)").fetchall()]
    keep = [c for c in panel.COLUMNS if c in cols]
    for need in ("FAMILYID", "STATE"):
        if need not in keep:
            raise RuntimeError(f"column {need} not in {raw.name}")
    select = f"""
        SELECT {year} AS year, {', '.join(map(quote, keep))}, '{raw.name}' AS source_file
        FROM read_csv('{raw.as_posix()}', {opts}, store_rejects=true, rejects_limit={REJECTS_LIMIT})
        WHERE upper(trim("STATE")) NOT IN ({', '.join(repr(s) for s in states)})"""
    fam = f"read_parquet('{panel.IDS_FAMILY.as_posix()}')"
    per = f"read_parquet('{panel.IDS_PERSON.as_posix()}')"
    try:
        con.sql(f"COPY ({panel.panel_records(select, keep, fam, per)}) TO '{tmp.as_posix()}' "
                f"(FORMAT parquet, COMPRESSION zstd, {panel.metadata(sig)})")
        n, by_fam, n_states = con.sql(f"""
            SELECT count(*), count(*) FILTER (WHERE trim(FAMILYID) IN (SELECT id FROM {fam})),
                   count(DISTINCT upper(trim(STATE)))
            FROM read_parquet('{tmp.as_posix()}')""").fetchall()[0]
        # error types and counts only: the rejects table also holds the raw lines
        rejects = con.sql("SELECT error_type, count(*) FROM reject_errors GROUP BY 1 ORDER BY 1").fetchall()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(out)
    rej = "; ".join(f"{t} {k:,}" for t, k in rejects) or "none"
    if sum(k for _, k in rejects) >= REJECTS_LIMIT:
        rej += f" (capped at {REJECTS_LIMIT:,})"
    missing = f"; columns not in the file: {', '.join(sorted(set(panel.COLUMNS) - set(keep)))}" \
        if set(panel.COLUMNS) - set(keep) else ""
    return (f"{year} ({raw.name}): {n:,} panel records outside the study states in {n_states} states "
            f"({by_fam:,} by FAMILYID, {n - by_fam:,} by an adult only); rejected rows: {rej}{missing}; "
            f"{(time.time() - t0) / 60:.1f} min")


def main() -> None:
    paths.require(paths.INFOUSA_RAW)
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    states = geo.study_states()
    panel.NATIONAL.mkdir(parents=True, exist_ok=True)

    sig_ids = panel.ids_signature(files, states)
    if panel.stored(panel.IDS_FAMILY) == sig_ids and panel.stored(panel.IDS_PERSON) == sig_ids:
        print("panel households and adults: up to date")
    else:
        print("collecting panel households and adults from the converted files", flush=True)
        build_ids(files, states, sig_ids)
    con = db.connect()
    n_fam = con.sql(f"SELECT count(*) FROM read_parquet('{panel.IDS_FAMILY.as_posix()}')").fetchall()[0][0]
    n_per = con.sql(f"SELECT count(*) FROM read_parquet('{panel.IDS_PERSON.as_posix()}')").fetchall()[0][0]
    print(f"panel: {n_fam:,} households, {n_per:,} adults", flush=True)

    raw = {y: f for y, v, f in paths.raw_files() if y in files and v == settings.PREFER_VERSION.get(y, "main")}
    absent = sorted(set(files) - set(raw))
    if absent:
        sys.exit(f"no raw national file for {', '.join(map(str, absent))} (the version prefer_version picks)")
    todo = []
    for y, f in sorted(raw.items()):
        sig = sig_ids + f"|{f.name}|{f.stat().st_size}|{','.join(panel.COLUMNS)}"
        done = panel.stored(panel.national_file(y)) == sig
        print(f"  {y} {f.relative_to(paths.INFOUSA_RAW)}  [{'done, skip' if done else 'read'}]")
        if not done:
            todo.append((y, f, sig))
    print(f"reading {len(todo)} national files, {paths.PARALLEL} at a time", flush=True)
    failed = 0
    with open(LOG, "a") as log, ThreadPoolExecutor(max_workers=paths.PARALLEL) as pool:
        jobs = {pool.submit(follow, y, f, states, sig): f for y, f, sig in todo}
        for job in as_completed(jobs):
            try:
                line = job.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                # first line only: later lines of a CSV error can quote a data row
                line = f"FAILED {jobs[job].name}: {type(e).__name__}: {str(e).splitlines()[0][:200]}"
            stamped = f"{datetime.now():%Y-%m-%d %H:%M}  {line}"
            print(stamped, flush=True)
            log.write(stamped + "\n")
            log.flush()
    if failed:
        sys.exit(f"{failed} file(s) failed; see {LOG}. Run the step again to retry them.")
    print(f"wrote {panel.NATIONAL}")


if __name__ == "__main__":
    main()
