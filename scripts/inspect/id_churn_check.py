"""Do infoUSA IDs change when people move? A name check within NC/SC.

For each pair of consecutive years from panel_first_year: primary families
in NC/SC whose FAMILYID is in neither the next year's NC/SC file nor its
step 07 file of records in other states ("vanished"). Their adults are looked
up in the next year's NC/SC file by first name, last name and birth year
(file year minus Age, one year either way). A match counts only if it is
unique: no one else has that name and birth year (+-1) in the first year, and
exactly one person has it in the next year.

- If many vanished households' adults turn up under other IDs, Data Axle
  reissues IDs (when people move, or when it rebuilds a record) and the
  households could be linked by name; if few do, they really are missing.
- Baseline: the same lookup for 1 in 20 households that kept their FAMILYID.
  Their adults are present, so the share found under the same IndividualID
  is how often the lookup finds someone who is there.
- Also: vanished households found the year after next (by name, or by their
  old FAMILYID coming back).

Not a pipeline step. Run on the server after steps 01 and 07:
    python scripts/inspect/id_churn_check.py [first year of pairs ...]
(default: every pair from panel_first_year). Names are used inside DuckDB
only; the outputs are counts: output/logs/id_churn_check.md and
output/tables/id_churn_check.csv.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import db, geo, panel, paths, settings  # noqa: E402
from flood_ra.address import address_key  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "id_churn_check.md"
TABLE = paths.REPO_ROOT / "output" / "tables" / "id_churn_check.csv"
SAMPLE = 20  # baseline: 1 in SAMPLE households that keep their FAMILYID
NEAR = "(VALUES (-1), (0), (1)) v(d)"  # birth years one either way


def columns(con, f: Path) -> set[str]:
    return {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()}


def name(col: str) -> str:
    return f"regexp_replace(upper(coalesce(CAST({col} AS VARCHAR), '')), '[^A-Z]', '', 'g')"


def adults_sql(f: Path, year: int, cols: set[str]) -> str:
    """One row per listed adult with a usable name and age: FAMILYID, person ID,
    name key (64-bit hash of first and last name), birth year, address key."""
    addr = address_key(cols, True, compact=True)
    parts = [f"""SELECT trim(FAMILYID) AS fid,
                        coalesce(nullif(trim(IndividualID_{k}), ''), trim(FAMILYID) || '#{k}') AS pid,
                        {name(f'First_Name_{k}')} AS fn, {name(f'Last_Name_{k}')} AS ln,
                        {year} - TRY_CAST(trim(CAST(Age_{k} AS VARCHAR)) AS INTEGER) AS birth, {addr} AS addr
                 FROM read_parquet('{f.as_posix()}')"""
             for k in range(1, 6)
             if all(c in cols for c in (f"IndividualID_{k}", f"First_Name_{k}", f"Last_Name_{k}", f"Age_{k}"))]
    if not parts:
        sys.exit(f"{f.name} has no IndividualID/First_Name/Last_Name/Age columns")
    return f"""SELECT fid, pid, hash(fn || '|' || ln) AS nk, birth, addr FROM ({' UNION ALL '.join(parts)})
               WHERE length(fn) >= 2 AND length(ln) >= 2 AND birth BETWEEN {year - 110} AND {year - 16}"""


def fids_sql(f: Path | None, nat: Path | None) -> str:
    """FAMILYIDs present in a year: NC/SC file plus the step 07 file, if any."""
    parts = [f"SELECT trim(FAMILYID) AS fid FROM read_parquet('{p.as_posix()}')"
             for p in (f, nat) if p is not None and p.exists()]
    return " UNION ALL ".join(parts) if parts else "SELECT NULL::VARCHAR AS fid WHERE false"


def one_pair(con, t: int, t1: int, t2: int | None, files: dict[int, Path], states: list[str]) -> dict:
    f0, f1, f2 = files[t], files[t1], files.get(t2) if t2 else None
    nat1 = panel.national_file(t1)
    nat2 = panel.national_file(t2) if t2 else None
    in_states = ", ".join(repr(s) for s in states)
    # primary families in t: vanished, and a sample of those that kept their FAMILYID
    con.sql(f"""CREATE OR REPLACE TEMP TABLE grp AS
        SELECT fid, CASE WHEN fid IN ({fids_sql(f1, nat1)}) THEN 'kept' ELSE 'vanished' END AS grp
        FROM (SELECT DISTINCT trim(FAMILYID) AS fid FROM read_parquet('{f0.as_posix()}')
              WHERE trim(PRIMARY_FAMILY_IND) = '1' AND upper(trim(STATE)) IN ({in_states})
                AND nullif(trim(FAMILYID), '') IS NOT NULL)""")
    n_fam, n_van = con.sql("SELECT count(*), count(*) FILTER (WHERE grp = 'vanished') FROM grp").fetchall()[0]
    con.sql(f"DELETE FROM grp WHERE grp = 'kept' AND hash(fid) % {SAMPLE} != 0")
    back_fid = (con.sql(f"""SELECT count(*) FROM grp WHERE grp = 'vanished'
                            AND fid IN ({fids_sql(f2, nat2)})""").fetchall()[0][0] if f2 else None)
    # their adults, and everyone in each year with the same name and a birth year within one
    c0, c1 = columns(con, f0), columns(con, f1)
    con.sql(f"CREATE OR REPLACE TEMP TABLE q AS SELECT g.grp, a.* FROM ({adults_sql(f0, t, c0)}) a JOIN grp g USING (fid)")
    con.sql(f"CREATE OR REPLACE TEMP TABLE qx AS SELECT q.fid AS qfid, q.pid AS qpid, q.nk, q.birth + d AS birth FROM q, {NEAR}")
    con.sql("CREATE OR REPLACE TEMP TABLE qk AS SELECT DISTINCT nk, birth FROM qx")
    near = {0: (f0, t, c0), 1: (f1, t1, c1)}
    if f2:
        near[2] = (f2, t2, columns(con, f2))
    for i, (f, y, cols) in near.items():
        con.sql(f"""CREATE OR REPLACE TEMP TABLE a{i} AS
            SELECT a.* FROM ({adults_sql(f, y, cols)}) a SEMI JOIN qk ON qk.nk = a.nk AND qk.birth = a.birth""")
    con.sql("CREATE OR REPLACE TEMP TABLE fids0 AS SELECT DISTINCT trim(FAMILYID) AS fid "
            f"FROM read_parquet('{f0.as_posix()}')")
    # per adult: someone else with the same key in t (not matchable), candidates in t1 and t2
    con.sql("""CREATE OR REPLACE TEMP TABLE dup AS
        SELECT DISTINCT qx.qfid, qx.qpid FROM qx JOIN a0 o ON o.nk = qx.nk AND o.birth = qx.birth WHERE o.pid != qx.qpid""")
    for i in near:
        if i == 0:
            continue
        con.sql(f"""CREATE OR REPLACE TEMP TABLE c{i} AS
            SELECT qx.qfid, qx.qpid, count(DISTINCT o.pid) AS n, any_value(o.pid) AS pid,
                   any_value(o.fid) AS fid, any_value(o.addr) AS addr
            FROM qx JOIN a{i} o ON o.nk = qx.nk AND o.birth = qx.birth GROUP BY ALL""")
    c2 = "c2" if f2 else "(SELECT NULL::VARCHAR AS qfid, NULL::VARCHAR AS qpid, NULL::BIGINT AS n WHERE false)"
    res = con.sql(f"""
        WITH r AS (
            SELECT q.grp, q.fid, q.pid,
                   d.qpid IS NULL AS matchable,
                   coalesce(c1.n, 0) AS n1, c1.pid = q.pid AS same_pid, c1.addr = q.addr AS same_addr,
                   c1.fid IN (SELECT fid FROM fids0) AS old_fid, coalesce(c2.n, 0) AS n2
            FROM q LEFT JOIN dup d ON d.qfid = q.fid AND d.qpid = q.pid
                   LEFT JOIN c1 ON c1.qfid = q.fid AND c1.qpid = q.pid
                   LEFT JOIN {c2} c2 ON c2.qfid = q.fid AND c2.qpid = q.pid),
        p AS (SELECT *, matchable AND n1 = 1 AS found1, matchable AND n1 = 0 AND n2 = 1 AS found2_only FROM r),
        h AS (SELECT grp, fid, bool_or(matchable) AS matchable, bool_or(found1) AS found1,
                     bool_or(found1 AND same_addr) AS found_same_addr,
                     bool_or(found1 AND NOT coalesce(same_addr, false)) AS found_new_addr,
                     bool_or(found1 AND old_fid) AS found_in_existing,
                     bool_or(found2_only) AND NOT bool_or(found1) AS found2_only
              FROM p GROUP BY ALL)
        SELECT 'adults' AS level, grp, count(*) FILTER (WHERE matchable) AS matchable,
               count(*) FILTER (WHERE found1) AS found, count(*) FILTER (WHERE found1 AND same_pid) AS same_pid,
               count(*) FILTER (WHERE found1 AND same_addr) AS same_addr,
               count(*) FILTER (WHERE found1 AND old_fid) AS in_existing,
               count(*) FILTER (WHERE matchable AND n1 > 1) AS ambiguous,
               count(*) FILTER (WHERE found2_only) AS found2_only, count(*) AS n
        FROM p GROUP BY ALL
        UNION ALL
        SELECT 'households', grp, count(*) FILTER (WHERE matchable), count(*) FILTER (WHERE found1), NULL,
               count(*) FILTER (WHERE found_same_addr), count(*) FILTER (WHERE found_in_existing), NULL,
               count(*) FILTER (WHERE found2_only), count(*)
        FROM h GROUP BY ALL""").df()
    out = {"year": t, "next_year": t1, "primary_families": n_fam, "vanished": n_van,
           "old_familyid_back_year_after": back_fid}
    for _, r in res.iterrows():
        for c in ("matchable", "found", "same_pid", "same_addr", "in_existing", "ambiguous", "found2_only", "n"):
            if pd.notna(r[c]) and not (c == "found2_only" and not f2):  # no year after to look in
                out[f"{r['grp']}_{r['level']}_{c}"] = int(r[c])
    for name_ in ("grp", "q", "qx", "qk", "a0", "a1", "a2", "fids0", "dup", "c1", "c2"):
        con.sql(f"DROP TABLE IF EXISTS {name_}")
    return out


def main() -> None:
    t0 = time.time()
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    states = geo.study_states()
    first = settings.PANEL_FIRST_YEAR or min(files)
    years = [y for y in sorted(files) if y >= first]
    pairs = [y for y in years[:-1] if y + 1 in files]
    if len(sys.argv) > 1:
        pairs = [int(a) for a in sys.argv[1:] if a.isdigit() and int(a) in pairs]
    missing_nat = [y + 1 for y in pairs if not panel.national_file(y + 1).exists()]
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    rows = []
    for t in pairs:
        rows.append(one_pair(con, t, t + 1, t + 2 if t + 2 in files else None, files, states))
        print(f"{t} -> {t + 1}: done", flush=True)
    d = pd.DataFrame(rows)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(TABLE, index=False)

    def col(c: str) -> pd.Series:
        return d[c] if c in d else pd.Series([pd.NA] * len(d))

    def share(a: str, b: str) -> pd.Series:
        return (col(a) / col(b).where(col(b) > 0)).map(pct)

    vh, va, ka = "vanished_households_", "vanished_adults_", "kept_adults_"
    van = pd.DataFrame({
        "years": d["year"].astype(str) + "->" + d["next_year"].astype(str),
        "vanished": (d["vanished"] / d["primary_families"]).map(pct),
        "with a matchable adult": share(vh + "matchable", vh + "n"),
        "found next year": share(vh + "found", vh + "matchable"),
        "of which same address": share(vh + "same_addr", vh + "found"),
        "of which in an older FAMILYID": share(vh + "in_existing", vh + "found"),
        "found only the year after": share(vh + "found2_only", vh + "matchable"),
        "old FAMILYID back the year after": (col("old_familyid_back_year_after") / d["vanished"]).map(pct)})
    adults = pd.DataFrame({
        "years": van["years"],
        "kept: found, same person ID": share(ka + "same_pid", ka + "matchable"),
        "kept: found, other person ID": ((col(ka + "found") - col(ka + "same_pid")) / col(ka + "matchable")).map(pct),
        "kept: ambiguous": share(ka + "ambiguous", ka + "matchable"),
        "vanished: found": share(va + "found", va + "matchable"),
        "vanished: found, same person ID": share(va + "same_pid", va + "found"),
        "vanished: ambiguous": share(va + "ambiguous", va + "matchable")})
    REPORT.write_text("\n".join([
        "# Do IDs change when people move? Name check within NC/SC (counts and shares only)", "",
        "Primary families in NC/SC whose FAMILYID is in neither the next year's NC/SC file nor the step 07 "
        "file of records in other states (vanished). Their adults are looked up in the next year's NC/SC "
        "file by first name, last name and birth year (file year minus Age, one year either way). A match "
        "counts only if it is unique: no one else has that name and birth year in the first year "
        "(matchable), and exactly one person has it in the next year (found). Baseline: the same lookup "
        f"for 1 in {SAMPLE} households that kept their FAMILYID. Moves out of NC/SC are not covered "
        "(names are only in the NC/SC files).", "",
        *([f"Notes: no step 07 file for {', '.join(map(str, missing_nat))}: households that moved out "
           "of NC/SC count as vanished in those years.", ""] if missing_nat else []),
        "## Households", "",
        "vanished: share of primary families. found next year: share of vanished households with a "
        "matchable adult who is found; of which: found at the same address (record rebuilt in place), "
        "or in a FAMILYID that already existed (joined another household). found only the year after: "
        "not found next year, found the year after. old FAMILYID back: share of vanished households "
        "whose FAMILYID reappears the year after.", "",
        *table(van),
        "## Adults", "",
        "kept: adults of households that kept their FAMILYID. Found under the same person ID is how often "
        "the lookup finds someone who is there; found under another ID shows how often IDs change (or "
        "names coincide) for people who did not move. vanished: adults of vanished households; same person "
        "ID would mean the household changed FAMILYID but kept the person's ID.", "",
        *table(adults),
        "How to read it: if 'vanished: found' is close to 'kept: found, same person ID', most vanished "
        "households are still in NC/SC under new IDs and could be linked by name; if it is far below, "
        "most are missing from the files.", ""]))
    print(f"wrote {REPORT} ({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
