"""Check sections 1 (migration) and 5 (age) of the Duke DPRC report "North
Carolina InfoUSA Analysis" (Davis Berlind, November 2019) against our files.

Not a pipeline step. Run on the server after step 01:
    python scripts/inspect/duke_report_check.py
Writes output/logs/duke_report_check.md and output/figures/duke_*.png
(aggregates and regression coefficients only). The family-year panel it
builds stays on the server in derived/duke_check/ (rebuilt on every run).

The report covers NC 2006-2018; our files start in 2007, so the replication
window is 2007-2018 (12 years, not 13). Like the report, a "household" is a
FAMILYID (all family records, subfamilies included); the primary-family
version is shown next to it.

Section 1 (migration):
- appearances: the number of years a FAMILYID is in the NC files;
- addresses: unique mailing addresses per FAMILYID (street, or PO box / rural
  route), as in the report's scatter (a family seen at one address has 1); also
  with the unit number, and unique LOCATIONIDs (Data Axle's dwelling ID);
- the two regressions of its table (appearances on household means; moves =
  addresses - 1 for families seen at least 4 times), by OLS with classical
  standard errors.
Section 5 (age): HEAD_HH_AGE_CODE by year, and against the age of
householder in ACS table B25007 (owners + renters).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import census, db, paths  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

STATE = "NC"
WINDOW = (2007, 2018)
REPORT = paths.LOG_DIR / "duke_report_check.md"
FIGURES = paths.REPO_ROOT / "output" / "figures"
WORK = paths.DERIVED / "duke_check"
GROUPS_FILE = paths.REPO_ROOT / "config" / "ethnicity_groups.yaml"

# CPI-U annual averages (BLS), to express FIND income in 2018 dollars as the report does
CPI = {2007: 207.342, 2008: 215.303, 2009: 214.537, 2010: 218.056, 2011: 224.939, 2012: 229.594,
       2013: 232.957, 2014: 236.736, 2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107}

AGE_CODES = {"A": "<25", "B": "25-29", "C": "30-34", "D": "35-39", "E": "40-44", "F": "45-49",
             "G": "50-54", "H": "55-59", "I": "60-64", "J": "65+ (inferred)", "K": "65-69",
             "L": "70-74", "M": "75+"}
# infoUSA age codes in the ACS B25007 age bands (disjoint). J (65+, inferred)
# fits none of them: it is shown on its own and in the derived 65+ shares.
BANDS = {"15-24": "A", "25-34": "BC", "35-44": "DE", "45-54": "FG", "55-59": "H", "60-64": "I",
         "65-74": "KL", "75+": "M"}

# Numbers printed in the report, for side-by-side comparison
REPORT_FAMILIES, REPORT_MEAN, REPORT_SD = 13_874_976, 4.5, 4.12
# Bar heights of the report's appearance histogram, read off the figure (approximate)
REPORT_APPEAR = {1: .32, 2: .18, 3: .095, 4: .065, 5: .048, 6: .04, 7: .033, 8: .028, 9: .026,
                 10: .025, 11: .022, 12: .027, 13: .105}
# Report table (Appearances; Moves): estimate per regressor
REPORT_REG = {
    "Intercept": (-1.31, 0.31), "Mean log HH income": (0.523, 0.11), "Mean own/rent status": (0.13, -0.07),
    "Mean children": (1.47, 0.02), "Mean marital status": (0.12, 0.01), "Mean length of residence": (0.19, -0.01),
    "Black": (0.62, 0.11), "Hispanic": (0.15, -0.01), "White": (0.27, 0.06), "Other": (-0.08, 0.04),
    "Age 25-29": (0.15, 0.19), "Age 30-34": (0.48, 0.27), "Age 35-39": (0.84, 0.30), "Age 40-44": (1.11, 0.25),
    "Age 45-49": (1.58, 0.19), "Age 50-54": (1.85, 0.15), "Age 55-59": (2.26, 0.14), "Age 60-64": (2.64, 0.13),
    "Age 65+ (inferred)": (2.84, 0.03), "Age 65-69": (3.05, 0.19), "Age 70-74": (3.23, 0.21), "Age 75+": (2.99, 0.28),
}
REPORT_R2 = (0.524, 0.101)
# 65+ share of heads in the report's age figure (all 65+ grouped), read off the bars (approximate)
REPORT_65 = {"2006-2010": {"infoUSA": 0.175, "ACS weighted": 0.205},
             "2012-2016": {"infoUSA": 0.235, "ACS weighted": 0.24}}


def norm(col: str, cols: set[str]) -> str:
    """SQL for one address part, upper-cased with single spaces ('' if absent)."""
    if col.startswith("left(") or col in cols:
        return f"coalesce(regexp_replace(upper(trim(CAST({col} AS VARCHAR))), '\\s+', ' ', 'g'), '')"
    return "''"


def address_key(cols: set[str], unit: bool) -> str:
    """SQL for a version-stable key (md5 hex) of a household's mailing address:
    the street address (house number, street, ZIP; optionally the unit), or for
    records without a street name the PO box or rural route and ZIP; NULL when
    neither is present."""
    zip5 = "left(trim(CAST(ZIP AS VARCHAR)), 5)"
    street = ["HOUSE_NUM", "STREET_PRE_DIR", "STREET_NAME", "STREET_SUFFIX", "STREET_POST_DIR", zip5]
    street += ["UNIT_NUM"] if unit else []
    box = ["BOX_TYPE", "BOX_NUM", "ROUTE_TYPE", "ROUTE_NUM", zip5]
    has_box = " OR ".join(f"nullif(trim(CAST({c} AS VARCHAR)), '') IS NOT NULL"
                          for c in ("BOX_NUM", "ROUTE_NUM") if c in cols) or "false"
    return (f"CASE WHEN nullif(trim(CAST(STREET_NAME AS VARCHAR)), '') IS NOT NULL "
            f"THEN md5(concat_ws('|', 'S', {', '.join(norm(c, cols) for c in street)})) "
            f"WHEN {has_box} THEN md5(concat_ws('|', 'B', {', '.join(norm(c, cols) for c in box)})) END")


def build_panel(con, files: dict[int, Path]) -> tuple[str, dict]:
    """One row per NC FAMILYID and year with the fields both sections use.
    Rebuilt on every run (one pass per yearly file), so it always matches the
    current files and code. A FAMILYID listed twice in a year keeps one row
    (the primary-family one first). Returns the panel and duplicates per year."""
    out = WORK / "panel"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*"):
        old.unlink()
    num = "TRY_CAST(trim({}) AS INTEGER)"
    dups = {}
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        cols = {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {src}").fetchall()}
        where = f"upper(trim(STATE)) = '{STATE}' AND nullif(trim(FAMILYID), '') IS NOT NULL"
        n, d = con.sql(f"SELECT count(*), count(*) - count(DISTINCT trim(FAMILYID)) FROM {src} WHERE {where}").fetchone()
        dups[year] = (n, d)
        p = out / f"{year}.parquet"
        con.sql(f"""COPY (
            SELECT {year} AS year, trim(FAMILYID) AS fid, coalesce(trim(PRIMARY_FAMILY_IND) = '1', false) AS prim,
                   {address_key(cols, False)} AS addr, {address_key(cols, True)} AS addr_unit,
                   nullif(trim(LOCATIONID), '') AS loc,
                   {num.format('FIND_DIV_1000')} AS inc, {num.format('OWNER_RENTER_STATUS')} AS own,
                   {num.format('CHILDRENHHCOUNT')} AS kids, {num.format('MARITAL_STATUS')} AS marital,
                   {num.format('LENGTH_OF_RESIDENCE')} AS lor,
                   nullif(nullif(upper(trim(Ethnicity_Code_1)), ''), '00') AS eth,
                   nullif(upper(trim(HEAD_HH_AGE_CODE)), '') AS age
            FROM {src} WHERE {where}
            QUALIFY row_number() OVER (PARTITION BY trim(FAMILYID) ORDER BY prim DESC, addr NULLS LAST) = 1
        ) TO '{p.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
        print(f"  {year}: {n - d:,} NC FAMILYIDs", flush=True)
    panel = "read_parquet([" + ", ".join(f"'{(out / f'{y}.parquet').as_posix()}'" for y in sorted(files)) + "])"
    return panel, dups


PARTS = 32  # the per-family summary runs in this many slices of FAMILYIDs, to bound memory and temp files


def families(con, panel: str, years: tuple[int, int], primary: bool) -> None:
    """Table fam: one row per FAMILYID over the window (universe: all or primary records)."""
    age_ok = ", ".join(f"'{c}'" for c in AGE_CODES)
    for part in range(PARTS):
        con.sql(("CREATE OR REPLACE TABLE fam AS " if part == 0 else "INSERT INTO fam ") + f"""
            SELECT fid, count(*) AS n_years, count(DISTINCT addr) AS n_addr,
                   count(DISTINCT addr_unit) AS n_addr_unit, count(DISTINCT loc) AS n_loc,
                   count(*) FILTER (WHERE loc IS NULL) AS n_loc_missing,
                   avg(ln(CASE WHEN inc > 0 THEN inc * to2018 END)) AS log_inc,
                   avg(CASE WHEN own BETWEEN 0 AND 9 THEN own END) AS own,
                   avg(CASE WHEN kids >= 0 THEN kids END) AS kids,
                   avg(CASE WHEN marital BETWEEN 0 AND 9 THEN marital END) AS marital,
                   avg(CASE WHEN lor >= 0 THEN lor END) AS lor,
                   arg_min(eth, p.year) FILTER (WHERE eth IS NOT NULL) AS eth,
                   arg_min(age, p.year) FILTER (WHERE age IN ({age_ok})) AS age
            FROM {panel} p LEFT JOIN cpi USING (year)
            WHERE p.year BETWEEN {years[0]} AND {years[1]} {"AND prim" if primary else ""}
                  AND hash(fid) % {PARTS} = {part}
            GROUP BY fid""")


def appearance_tables(con, label: str) -> tuple[list, pd.DataFrame]:
    """Summary row and the distribution of appearances. Address statistics use
    families with at least one usable address (street, PO box or route)."""
    n, mean, sd, no_addr, addr, loc, two_addr_one_loc = con.sql("""
        SELECT count(*), avg(n_years), stddev_samp(n_years), count(*) FILTER (WHERE n_addr = 0),
               avg(n_addr) FILTER (WHERE n_addr >= 1), avg(n_loc) FILTER (WHERE n_loc_missing = 0),
               count(*) FILTER (WHERE n_addr >= 2 AND n_loc = 1 AND n_loc_missing = 0)
                 / nullif(count(*) FILTER (WHERE n_addr >= 2 AND n_loc_missing = 0), 0)
        FROM fam""").fetchone()
    dist = con.sql("""
        SELECT n_years AS appearances, count(*) AS families,
               avg(n_addr) FILTER (WHERE n_addr >= 1) AS addresses,
               avg(n_addr - 1) FILTER (WHERE n_addr >= 1) AS moves,
               avg(n_addr_unit) FILTER (WHERE n_addr >= 1) AS addresses_with_unit,
               avg(n_loc) FILTER (WHERE n_loc_missing = 0) AS locationids,
               count(*) FILTER (WHERE n_addr >= 2) / nullif(count(*) FILTER (WHERE n_addr >= 1), 0) AS moved
        FROM fam GROUP BY 1 ORDER BY 1""").df()
    dist["share"] = dist["families"] / dist["families"].sum()
    return [label, f"{n:,}", f"{mean:.2f}", f"{sd:.2f}", pct(no_addr / n if n else None), f"{addr:.2f}",
            f"{loc:.2f}" if loc is not None else "", pct(two_addr_one_loc)], dist


REGRESSORS = [("const", "Intercept"), ("log_inc", "Mean log HH income"), ("own", "Mean own/rent status"),
              ("kids", "Mean children"), ("marital", "Mean marital status"), ("lor", "Mean length of residence"),
              ("r_black", "Black"), ("r_hispanic", "Hispanic"), ("r_white", "White"), ("r_other", "Other"),
              ("r_missing", "Race missing")] + [(f"a_{c}", f"Age {AGE_CODES[c]}") for c in "BCDEFGHIJKLM"]


def regressions(con) -> tuple[pd.DataFrame, list[str]]:
    """OLS of appearances (all families) and of moves = unique addresses - 1
    (families seen 4+ times with an address) on household means, race (base:
    Asian) and the head's first known age code (base: under 25), from
    cross-product sums computed in DuckDB. Also the mean of y implied by the
    report's coefficients at our regressor means, a check on units."""
    groups = {str(k).upper(): str(v).lower()
              for k, v in (yaml.load(GROUPS_FILE.read_text(), Loader=yaml.BaseLoader) or {}).items()}
    con.register("grp_df", pd.DataFrame({"code": list(groups), "grp": list(groups.values())}))
    race = "CASE WHEN eth IS NULL THEN 'missing' ELSE coalesce(g.grp, 'other') END"
    dummies = [f"({race} = '{r}')::DOUBLE AS r_{r}" for r in ("black", "hispanic", "white", "other", "missing")]
    dummies += [f"(age = '{c}')::DOUBLE AS a_{c}" for c in "BCDEFGHIJKLM"]
    con.sql(f"""CREATE OR REPLACE TABLE reg AS
        SELECT n_years::DOUBLE AS y_app, (n_addr - 1)::DOUBLE AS y_mov, n_years >= 4 AND n_addr >= 1 AS mov_sample,
               1.0 AS const,
               log_inc, own, kids, marital, lor, {", ".join(dummies)}
        FROM fam LEFT JOIN grp_df g ON g.code = fam.eth
        WHERE log_inc IS NOT NULL AND own IS NOT NULL AND kids IS NOT NULL AND marital IS NOT NULL
              AND lor IS NOT NULL AND age IS NOT NULL""")
    cols = [c for c, _ in REGRESSORS]
    out, r2, ns, ymean, implied, notes = {}, [], [], [], [], []
    for y, where in (("y_app", "true"), ("y_mov", "mov_sample")):
        sums = [f"sum({a} * {b})" for i, a in enumerate(cols) for b in cols[i:]]
        sums += [f"sum({a} * {y})" for a in cols] + [f"sum({y} * {y})", f"sum({y})", "count(*)"]
        vals = con.sql(f"SELECT {', '.join(sums)} FROM reg WHERE {where}").fetchone()
        k = len(cols)
        xtx = np.zeros((k, k))
        it = iter(vals)
        for i in range(k):
            for j in range(i, k):
                xtx[i, j] = xtx[j, i] = next(it) or 0.0
        xty = np.array([next(it) or 0.0 for _ in range(k)])
        yty, ysum, n = next(it) or 0.0, next(it) or 0.0, next(it)
        keep = [i for i in range(k) if xtx[i, i] > 0]  # drop categories absent from the data
        a, b = xtx[np.ix_(keep, keep)], xty[keep]
        if np.linalg.matrix_rank(a) < len(keep):
            notes.append(f"regression of {y}: regressors are collinear; estimates are not identified")
        inv = np.linalg.pinv(a)
        beta = inv @ b
        ssr = yty - beta @ b
        sst = yty - ysum ** 2 / n if n else np.nan
        se = np.sqrt(np.maximum(np.diag(inv) * ssr / max(n - len(keep), 1), 0))
        est = {cols[i]: (beta[m], se[m]) for m, i in enumerate(keep)}
        out[y] = est
        r2.append(1 - ssr / sst if sst else np.nan)
        ns.append(n)
        ymean.append(ysum / n if n else np.nan)
        xbar = {c: xtx[0, i] / n for i, c in enumerate(cols)} if n else {}
        slot = 0 if y == "y_app" else 1
        implied.append(sum(REPORT_REG[name][slot] * xbar.get(c, 0) for c, name in REGRESSORS if name in REPORT_REG))
    rows = []
    for c, name in REGRESSORS:
        rep = REPORT_REG.get(name, ("", ""))
        cell = lambda y: (f"{out[y][c][0]:.3f} ({out[y][c][1]:.3f})" if c in out[y] else "")
        rows.append([name, rep[0], cell("y_app"), rep[1], cell("y_mov")])
    rows.append(["R2", REPORT_R2[0], f"{r2[0]:.3f}", REPORT_R2[1], f"{r2[1]:.3f}"])
    rows.append(["N", "", f"{ns[0]:,}", "", f"{ns[1]:,}"])
    rows.append(["mean of y", "", f"{ymean[0]:.2f}", "", f"{ymean[1]:.2f}"])
    rows.append(["mean of y implied by the report's coefficients at our means",
                 "", f"{implied[0]:.2f}", "", f"{implied[1]:.2f}"])
    df = pd.DataFrame(rows, columns=["regressor", "report: appearances", "ours: appearances (SE)",
                                     "report: moves", "ours: moves = addresses - 1 (SE)"])
    con.sql("DROP TABLE reg")
    con.unregister("grp_df")
    return df, notes


def age_tables(con, panel: str) -> pd.DataFrame:
    """HEAD_HH_AGE_CODE counts by year (all and primary records), one column per code."""
    d = con.sql(f"""SELECT year, prim, coalesce(age, '(missing)') AS age, count(*) AS n
                    FROM {panel} GROUP BY ALL""").df()
    out = []
    for universe, sub in (("all", d), ("primary", d[d["prim"]])):
        w = sub.pivot_table(index="year", columns="age", values="n", aggfunc="sum", fill_value=0)
        w["universe"] = universe
        out.append(w.reset_index())
    return pd.concat(out, ignore_index=True)


def band_shares(counts: pd.Series, j_as_missing: bool = False) -> dict:
    """Shares among heads with a known age code: the disjoint BANDS, J on its
    own, and the derived 65+ and '75+ incl. J'. With j_as_missing, J is left
    out of the denominator (a sensitivity check)."""
    codes = [c for c in AGE_CODES if not (j_as_missing and c == "J")]
    known = sum(counts.get(c, 0) for c in codes)
    share = lambda cs: (sum(counts.get(c, 0) for c in cs if c in codes) / known if known else np.nan)
    res = {b: share(cs) for b, cs in BANDS.items()}
    res["J"] = share("J")
    res["65+"] = share("JKLM")
    res["75+ incl. J"] = share("JM")
    return res


ACS_COLS = ["15-24", "25-34", "35-44", "45-54", "55-59", "60-64", "65-74", "75+", "65+"]


def acs_band_shares(acs: pd.DataFrame) -> pd.DataFrame:
    need = ["households"] + [f"{t}_{b}" for t in ("owner", "renter") for b in census.AGE_BANDS]
    if not len(acs) or any(c not in acs for c in need):
        return pd.DataFrame(columns=["year"] + ACS_COLS)
    a = acs.copy()
    for b in census.AGE_BANDS:
        a[b] = a[f"owner_{b}"] + a[f"renter_{b}"]
    tot = a["households"]
    res = pd.DataFrame({"year": a["year"]})
    for b in ("15-24", "25-34", "35-44", "45-54", "55-59", "60-64", "65-74"):
        res[b] = a[b] / tot
    res["75+"] = (a["75-84"] + a["85+"]) / tot
    res["65+"] = (a["65-74"] + a["75-84"] + a["85+"]) / tot
    return res


def plot(dist_all: pd.DataFrame, dist_prim: pd.DataFrame, windows: dict, path_app: Path, path_age: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(dist_all["appearances"] - 0.2, dist_all["share"], width=0.4, color="#1f5fa8",
           label=f"ours, all family records {WINDOW[0]}-{WINDOW[1]}")
    ax.bar(dist_prim["appearances"] + 0.2, dist_prim["share"], width=0.4, color="#9ab8de",
           label="ours, primary families")
    ax.plot(list(REPORT_APPEAR), list(REPORT_APPEAR.values()), "o", color="#c8611c",
            label="report, 2006-2018 (read off its figure)")
    ax.set_xlabel("years in the NC files (report: up to 13; ours: up to 12)")
    ax.set_ylabel("share of FAMILYIDs")
    ax.set_xticks(range(1, 14))
    ax.legend()
    ax.set_title("How many years each FAMILYID appears")
    fig.tight_layout()
    fig.savefig(path_app, dpi=130)
    plt.close(fig)

    cats = list(BANDS) + ["J"]
    labels = list(BANDS) + ["J: 65+\n(inferred)"]
    styles = {"ACS": "#444444", "infoUSA all": "#1f5fa8", "infoUSA primary": "#9ab8de"}
    fig, axes = plt.subplots(1, len(windows), figsize=(8 * len(windows), 5), sharey=True)
    handles = {}
    any_acs = False
    for ax, (label, src) in zip(np.atleast_1d(axes), windows.items()):
        series = [k for k in styles if k in src and not all(np.isnan(v) for v in src[k].values())]
        any_acs |= "ACS" in series
        width = 0.8 / max(len(series), 1)
        x = np.arange(len(cats))
        for k, name in enumerate(series):
            vals = [src[name].get(c, np.nan) for c in cats]
            h = ax.bar(x + (k - (len(series) - 1) / 2) * width, vals, width=width, color=styles[name], label=name)
            handles[name] = h
        ax.set_xticks(x, labels)
        ax.set_title(label + ("" if "ACS" in series else " (ACS not available)"))
        ax.set_xlabel("age of head of household")
    np.atleast_1d(axes)[0].set_ylabel("share of households with a known age")
    np.atleast_1d(axes)[0].legend(list(handles.values()), list(handles))
    fig.suptitle("Age of head of household: infoUSA (NC)" + (" vs ACS householders (B25007)" if any_acs else ""))
    fig.tight_layout()
    fig.savefig(path_age, dpi=130)
    plt.close(fig)


def main() -> None:
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    FIGURES.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    con.sql("CREATE OR REPLACE TABLE cpi AS SELECT * FROM (VALUES "
            + ", ".join(f"({y}, {CPI[2018] / v}::DOUBLE)" for y, v in CPI.items()) + ") t(year, to2018)")
    print("building the family-year panel", flush=True)
    panel, dups = build_panel(con, files)
    years = sorted(files)
    notes = []
    for lo, hi in (WINDOW, (years[0], years[-1])):
        gap = [y for y in range(lo, hi + 1) if y not in files]
        if gap:
            notes.append(f"no file for {', '.join(map(str, gap))} within {lo}-{hi}: fewer appearances are possible")
    n_dup = sum(d for _, d in dups.values())
    notes.append(f"FAMILYIDs listed more than once in a year: {n_dup:,} records in all years "
                 f"({pct(n_dup / sum(n for n, _ in dups.values()))}); one row each was kept, primary family first")

    # Section 1: appearances and addresses
    print("appearances and addresses", flush=True)
    summary, dists, reg = [], {}, None
    for label, yrs, primary in ((f"all records {WINDOW[0]}-{WINDOW[1]}", WINDOW, False),
                                (f"primary families {WINDOW[0]}-{WINDOW[1]}", WINDOW, True),
                                (f"all records {years[0]}-{years[-1]}", (years[0], years[-1]), False),
                                (f"primary families {years[0]}-{years[-1]}", (years[0], years[-1]), True)):
        families(con, panel, yrs, primary)
        row, dist = appearance_tables(con, label)
        summary.append(row)
        dists[label] = dist
        if reg is None and not primary and yrs == WINDOW:
            print("regressions", flush=True)
            reg, reg_notes = regressions(con)
            notes += reg_notes
        print(f"  {label}: done", flush=True)
    con.sql("DROP TABLE IF EXISTS fam")
    summary.insert(0, ["report: NC 2006-2018", f"{REPORT_FAMILIES:,}", f"{REPORT_MEAN:.2f}", f"{REPORT_SD:.2f}",
                       "", "", "", ""])
    d_all = dists[f"all records {WINDOW[0]}-{WINDOW[1]}"]
    d_prim = dists[f"primary families {WINDOW[0]}-{WINDOW[1]}"]

    # Section 5: age
    print("age", flush=True)
    ages = age_tables(con, panel)
    acs, n_acs = census.state_series(years, [census_fips()], census.AGE_VARS, "acs1_state_age.csv")
    notes += n_acs
    acs_b = acs_band_shares(acs)
    by_year, windows = [], {}
    for _, r in ages.iterrows():
        s = band_shares(r)
        sj = band_shares(r, j_as_missing=True)
        known = sum(r.get(c, 0) for c in AGE_CODES)
        tot = sum(v for c, v in r.items() if c not in ("year", "universe"))
        a = acs_b[acs_b["year"] == r["year"]]
        acs_cell = lambda col: pct(a[col].iloc[0]) if len(a) else ""
        by_year.append([int(r["year"]), r["universe"], pct(1 - known / tot if tot else np.nan), pct(s["J"]),
                        pct(s["15-24"]), pct(s["25-34"] + s["35-44"]), pct(s["65-74"]), pct(s["75+"]),
                        pct(s["75+ incl. J"]), pct(s["65+"]), pct(sj["65+"]),
                        acs_cell("15-24"), pct((a["25-34"] + a["35-44"]).iloc[0]) if len(a) else "",
                        acs_cell("65-74"), acs_cell("75+"), acs_cell("65+")])
    by_year = pd.DataFrame(by_year, columns=[
        "year", "records", "age missing", "J of known", "<25", "25-44", "65-74 (K,L)", "75+ (M)", "75+ incl. J",
        "65+", "65+ if J missing", "ACS <25", "ACS 25-44", "ACS 65-74", "ACS 75+", "ACS 65+"]
    ).sort_values(["records", "year"])
    win_rows = []
    for wlabel, (y0, y1) in (("2006-2010", (2007, 2010)), ("2012-2016", (2012, 2016))):
        key = f"{wlabel} (ours: {y0}-{y1})"
        windows[key] = {}
        for universe in ("all", "primary"):
            sub = ages[(ages["universe"] == universe) & ages["year"].between(y0, y1)]
            totals = sub.drop(columns=["year", "universe"]).sum()
            windows[key][f"infoUSA {universe}"] = band_shares(totals)
            if universe == "all":
                j_missing = band_shares(totals, j_as_missing=True)["65+"]
        a = acs_b[acs_b["year"].between(y0, y1)]
        if len(a):
            windows[key]["ACS"] = a[ACS_COLS].mean().to_dict()
        w = windows[key]
        win_rows.append([wlabel, pct(REPORT_65[wlabel]["infoUSA"]), pct(w["infoUSA all"]["65+"]),
                         pct(w["infoUSA primary"]["65+"]), pct(j_missing), pct(REPORT_65[wlabel]["ACS weighted"]),
                         pct(w.get("ACS", {}).get("65+"))])

    plot(d_all, d_prim, windows, FIGURES / "duke_appearances.png", FIGURES / "duke_age.png")

    fmt_dist = lambda d: d.assign(share=d["share"].map(pct), families=d["families"].map("{:,}".format),
                                  moved=d["moved"].map(pct)).round(2)
    REPORT.write_text("\n".join([
        "# Duke DPRC report (Berlind 2019), sections 1 and 5, against our files (aggregates only)", "",
        f"NC records. The report covers 2006-2018; our files start in 2007, so its numbers are compared "
        f"with {WINDOW[0]}-{WINDOW[1]} (12 years instead of 13: fewer appearances are possible). Like the "
        "report, a household is a FAMILYID (all family records, subfamilies included); primary families "
        "are shown too. Report values marked 'read off its figure' are approximate.", "",
        "Notes: " + "; ".join(notes) + ".", "",
        "## 1. Families and appearances", "",
        "families: distinct FAMILYIDs. appearances: years in the NC files. no address: share of families "
        "with no usable address in any year (left out of the address statistics). addresses: distinct "
        "mailing addresses per FAMILYID (house number, street and ZIP, or PO box / rural route and ZIP), "
        "so a family never seen to move has 1. LOCATIONIDs: distinct Data Axle dwelling IDs (families "
        "with a LOCATIONID in every year). last column: of those families with 2+ addresses, the share "
        "whose LOCATIONID never changed (a hint that some 'moves' are re-spelled addresses).", "",
        *table(pd.DataFrame(summary, columns=["universe", "families", "mean appearances", "SD", "no address",
                                              "mean addresses", "mean LOCATIONIDs",
                                              "2+ addresses, 1 LOCATIONID"])),
        f"### Distribution of appearances, all records {WINDOW[0]}-{WINDOW[1]}", "",
        "Report bars (2006-2018, approximate): " + ", ".join(f"{k}: {pct(v)}" for k, v in REPORT_APPEAR.items())
        + ". Among families with an address: moves = addresses - 1; moved = share with 2+ addresses.", "",
        *table(fmt_dist(d_all)),
        f"### Primary families {WINDOW[0]}-{WINDOW[1]}", "",
        *table(fmt_dist(d_prim)),
        "## 1b. The report's regressions", "",
        f"All family records {WINDOW[0]}-{WINDOW[1]}, one row per FAMILYID with complete data. Regressors are "
        "means over the family's years (log income in $1,000 of 2018, CPI-U; own/rent and marital codes "
        "0-9 as numbers; CHILDRENHHCOUNT; LENGTH_OF_RESIDENCE), race from the first known "
        "Ethnicity_Code_1 grouped with config/ethnicity_groups.yaml (base: Asian; the report's race "
        "variable may come from its wru estimates and has Mixed, Native American and Pacific Islander "
        "groups we cannot form), and the head's first known age code (earliest year with a code A-M; "
        "base: under 25; J = 65+ inferred). Moves: unique addresses - 1, families seen 4+ times with an "
        "address. The report's scatter counts addresses, but its moves coefficients imply a mean outcome "
        "well below 1, so its regression must count moves. OLS, classical SEs. Last row: the mean "
        "outcome the report's coefficients would give at our regressor means; far from our mean, it "
        "points to different units or variable definitions.", "",
        *table(reg),
        "## 5. Age of the head of household", "",
        "HEAD_HH_AGE_CODE by year: missing share; J (65+ inferred per the Data Axle dictionary) among "
        "known codes; shares of ACS age bands among known codes (65-74 = K+L, 75+ = M; the report's "
        "second grouping puts J with 75+); 65+ = J+K+L+M; and 65+ if J is treated as missing, a "
        "sensitivity check because an earlier project Q&A note treated J as missing. ACS: age of "
        "householder, B25007, 1-year.", "",
        *table(by_year),
        "### Report's 5-year windows: share of heads 65+", "",
        *table(pd.DataFrame(win_rows, columns=["window", "report infoUSA (figure)", "ours all", "ours primary",
                                               "ours all, J missing", "report ACS weighted (figure)",
                                               "ACS 1-year mean"])),
        "Figures: `output/figures/duke_appearances.png`, `output/figures/duke_age.png`.", "",
    ]))
    print(f"wrote {REPORT}")


def census_fips() -> str:
    from flood_ra import geo
    return geo.STATE_FIPS[STATE]


if __name__ == "__main__":
    main()
