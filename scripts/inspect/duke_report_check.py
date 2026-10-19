"""Check sections 1 (migration) and 5 (age) of the Duke DPRC report "North
Carolina InfoUSA Analysis" (Davis Berlind, November 2019) against our files.

Not a pipeline step. Run on the server after step 01:
    python scripts/inspect/duke_report_check.py
Writes output/logs/duke_report_check.md and output/figures/duke_*.png
(aggregates and regression coefficients only). The family-year panel it
builds stays on the server in derived/duke_check/.

The report covers NC 2006-2018; our files start in 2007, so the replication
window is 2007-2018 (12 years, not 13). Like the report, a "household" is a
FAMILYID (all family records, subfamilies included); the primary-family
version is shown next to it.

Section 1 (migration):
- appearances: the number of years a FAMILYID is in the NC files;
- "moves": the report counts unique street addresses per FAMILYID (a family
  seen at one address has 1), so we do too, and also give moves = addresses - 1,
  the same with the unit number, and unique LOCATIONIDs (Data Axle's dwelling ID);
- the two regressions of its table (appearances on household means; addresses
  for families seen at least 4 times), by OLS with classical standard errors.
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
# infoUSA age codes in the ACS B25007 age bands
BANDS = {"15-24": "A", "25-34": "BC", "35-44": "DE", "45-54": "FG", "55-59": "H", "60-64": "I",
         "65+": "JKLM"}

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


def street(*parts: str) -> str:
    """SQL hash of a normalized street address (NULL without a street name)."""
    fields = ", ".join(f"coalesce(regexp_replace(upper(trim(CAST({p} AS VARCHAR))), '\\s+', ' ', 'g'), '')"
                       for p in parts)
    return f"CASE WHEN nullif(trim(STREET_NAME), '') IS NOT NULL THEN hash(concat_ws('|', {fields})) END"


ADDR = street("HOUSE_NUM", "STREET_PRE_DIR", "STREET_NAME", "STREET_SUFFIX", "STREET_POST_DIR", "left(trim(ZIP), 5)")
ADDR_UNIT = street("HOUSE_NUM", "STREET_PRE_DIR", "STREET_NAME", "STREET_SUFFIX", "STREET_POST_DIR",
                   "left(trim(ZIP), 5)", "UNIT_NUM")


def build_panel(con, files: dict[int, Path]) -> str:
    """One row per NC family record and year, with the fields both sections use."""
    out = WORK / "panel"
    out.mkdir(parents=True, exist_ok=True)
    num = "TRY_CAST(trim({}) AS INTEGER)"
    for year, f in files.items():
        p = out / f"{year}.parquet"
        if p.exists() and p.stat().st_mtime > f.stat().st_mtime:
            continue
        tmp = p.with_suffix(".tmp")
        con.sql(f"""COPY (
            SELECT {year} AS year, trim(FAMILYID) AS fid, coalesce(trim(PRIMARY_FAMILY_IND) = '1', false) AS prim,
                   {ADDR} AS addr, {ADDR_UNIT} AS addr_unit, nullif(trim(LOCATIONID), '') AS loc,
                   {num.format('FIND_DIV_1000')} AS inc, {num.format('OWNER_RENTER_STATUS')} AS own,
                   {num.format('CHILDRENHHCOUNT')} AS kids, {num.format('MARITAL_STATUS')} AS marital,
                   {num.format('LENGTH_OF_RESIDENCE')} AS lor,
                   nullif(nullif(upper(trim(Ethnicity_Code_1)), ''), '00') AS eth,
                   nullif(upper(trim(HEAD_HH_AGE_CODE)), '') AS age
            FROM read_parquet('{f.as_posix()}')
            WHERE upper(trim(STATE)) = '{STATE}' AND nullif(trim(FAMILYID), '') IS NOT NULL
        ) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
        tmp.replace(p)
        print(f"  {year}: panel rows written", flush=True)
    return f"read_parquet('{(out / '*.parquet').as_posix()}')"


def families(con, panel: str, years: tuple[int, int], primary: bool) -> None:
    """Table fam: one row per FAMILYID over the window (universe: all or primary records)."""
    con.sql("CREATE OR REPLACE TABLE cpi AS SELECT * FROM (VALUES "
            + ", ".join(f"({y}, {CPI[2018] / v}::DOUBLE)" for y, v in CPI.items()) + ") t(year, to2018)")
    age_ok = ", ".join(f"'{c}'" for c in AGE_CODES)
    con.sql(f"""CREATE OR REPLACE TABLE fam AS
        SELECT fid, count(DISTINCT p.year) AS n_years, count(DISTINCT addr) AS n_addr,
               count(DISTINCT addr_unit) AS n_addr_unit, count(DISTINCT loc) AS n_loc,
               avg(ln(inc * to2018)) FILTER (WHERE inc > 0) AS log_inc,
               avg(own) FILTER (WHERE own BETWEEN 0 AND 9) AS own,
               avg(kids) FILTER (WHERE kids >= 0) AS kids,
               avg(marital) FILTER (WHERE marital BETWEEN 0 AND 9) AS marital,
               avg(lor) FILTER (WHERE lor >= 0) AS lor,
               arg_min(eth, p.year) FILTER (WHERE eth IS NOT NULL) AS eth,
               arg_min(age, p.year) FILTER (WHERE age IN ({age_ok})) AS age
        FROM {panel} p LEFT JOIN cpi USING (year)
        WHERE p.year BETWEEN {years[0]} AND {years[1]} {"AND prim" if primary else ""}
        GROUP BY fid""")


def appearance_tables(con, label: str) -> tuple[list, pd.DataFrame]:
    n, mean, sd, addr, loc, two_addr_one_loc = con.sql("""
        SELECT count(*), avg(n_years), stddev_samp(n_years), avg(n_addr), avg(n_loc),
               count(*) FILTER (WHERE n_addr >= 2 AND n_loc = 1) / nullif(count(*) FILTER (WHERE n_addr >= 2), 0)
        FROM fam""").fetchone()
    dist = con.sql("""
        SELECT n_years AS appearances, count(*) AS families, avg(n_addr) AS addresses,
               avg(n_addr - 1) FILTER (WHERE n_addr >= 1) AS moves, avg(n_addr_unit) AS addresses_with_unit,
               avg(n_loc) AS locationids, count(*) FILTER (WHERE n_addr >= 2) / count(*) AS moved
        FROM fam GROUP BY 1 ORDER BY 1""").df()
    dist["share"] = dist["families"] / dist["families"].sum()
    return [label, f"{n:,}", f"{mean:.2f}", f"{sd:.2f}", f"{addr:.2f}", f"{loc:.2f}", pct(two_addr_one_loc)], dist


REGRESSORS = [("const", "Intercept"), ("log_inc", "Mean log HH income"), ("own", "Mean own/rent status"),
              ("kids", "Mean children"), ("marital", "Mean marital status"), ("lor", "Mean length of residence"),
              ("r_black", "Black"), ("r_hispanic", "Hispanic"), ("r_white", "White"), ("r_other", "Other"),
              ("r_missing", "Race missing")] + [(f"a_{c}", f"Age {AGE_CODES[c]}") for c in "BCDEFGHIJKLM"]


def regressions(con) -> tuple[pd.DataFrame, list, int, int]:
    """OLS of appearances (all families) and of unique addresses (families seen
    4+ times) on household means, race (base: Asian) and head age at first
    appearance (base: under 25), from cross-product sums computed in DuckDB."""
    groups = {str(k).upper(): str(v).lower()
              for k, v in (yaml.load(GROUPS_FILE.read_text(), Loader=yaml.BaseLoader) or {}).items()}
    con.register("grp_df", pd.DataFrame({"code": list(groups), "grp": list(groups.values())}))
    race = "CASE WHEN eth IS NULL THEN 'missing' ELSE coalesce(g.grp, 'other') END"
    dummies = [f"({race} = '{r}')::DOUBLE AS r_{r}" for r in ("black", "hispanic", "white", "other", "missing")]
    dummies += [f"(age = '{c}')::DOUBLE AS a_{c}" for c in "BCDEFGHIJKLM"]
    con.sql(f"""CREATE OR REPLACE TABLE reg AS
        SELECT n_years::DOUBLE AS y_app, n_addr::DOUBLE AS y_mov, n_years >= 4 AS mov_sample, 1.0 AS const,
               log_inc, own, kids, marital, lor, {", ".join(dummies)}
        FROM fam LEFT JOIN grp_df g ON g.code = fam.eth
        WHERE log_inc IS NOT NULL AND own IS NOT NULL AND kids IS NOT NULL AND marital IS NOT NULL
              AND lor IS NOT NULL AND age IS NOT NULL""")
    cols = [c for c, _ in REGRESSORS]
    out, r2, ns = {}, [], []
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
        inv = np.linalg.pinv(a)
        beta = inv @ b
        ssr = yty - beta @ b
        sst = yty - ysum ** 2 / n if n else np.nan
        se = np.sqrt(np.maximum(np.diag(inv) * ssr / max(n - len(keep), 1), 0))
        est = {cols[i]: (beta[m], se[m]) for m, i in enumerate(keep)}
        out[y] = est
        r2.append(1 - ssr / sst if sst else np.nan)
        ns.append(n)
    rows = []
    for c, name in REGRESSORS:
        rep = REPORT_REG.get(name, ("", ""))
        cell = lambda y: (f"{out[y][c][0]:.3f} ({out[y][c][1]:.3f})" if c in out[y] else "")
        rows.append([name, rep[0], cell("y_app"), rep[1], cell("y_mov")])
    rows.append(["R2", REPORT_R2[0], f"{r2[0]:.3f}", REPORT_R2[1], f"{r2[1]:.3f}"])
    rows.append(["N", "", f"{ns[0]:,}", "", f"{ns[1]:,}"])
    df = pd.DataFrame(rows, columns=["regressor", "report: appearances", "ours: appearances (SE)",
                                     "report: moves", "ours: addresses (SE)"])
    return df, r2, ns[0], ns[1]


def age_tables(con, panel: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """HEAD_HH_AGE_CODE shares by year (all and primary records)."""
    d = con.sql(f"""SELECT year, prim, coalesce(age, '(missing)') AS age, count(*) AS n
                    FROM {panel} GROUP BY ALL""").df()
    out = []
    for universe, sub in (("all", d), ("primary", d[d["prim"]])):
        w = sub.pivot_table(index="year", columns="age", values="n", aggfunc="sum", fill_value=0)
        w["universe"] = universe
        out.append(w.reset_index())
    return pd.concat(out, ignore_index=True), d


def band_shares(counts: pd.Series, j_as_missing: bool = False) -> dict:
    """Shares of the ACS age bands among heads with a known age code."""
    codes = [c for c in AGE_CODES if not (j_as_missing and c == "J")]
    known = sum(counts.get(c, 0) for c in codes)
    return {b: (sum(counts.get(c, 0) for c in cs if c in codes) / known if known else np.nan)
            for b, cs in BANDS.items()}


def acs_band_shares(acs: pd.DataFrame) -> pd.DataFrame:
    need = ["households"] + [f"{t}_{b}" for t in ("owner", "renter") for b in census.AGE_BANDS]
    if not len(acs) or any(c not in acs for c in need):
        return pd.DataFrame(columns=["year"] + list(BANDS))
    a = acs.copy()
    for b in census.AGE_BANDS:
        a[b] = a[f"owner_{b}"] + a[f"renter_{b}"]
    tot = a["households"]
    res = pd.DataFrame({"year": a["year"]})
    for b in ("15-24", "25-34", "35-44", "45-54", "55-59", "60-64"):
        res[b] = a[b] / tot
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
    ax.set_xlabel("years in the NC files")
    ax.set_ylabel("share of FAMILYIDs")
    ax.set_xticks(range(1, 14))
    ax.legend()
    ax.set_title("How many years each FAMILYID appears")
    fig.tight_layout()
    fig.savefig(path_app, dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(windows), figsize=(7 * len(windows), 5), sharey=True)
    for ax, (label, src) in zip(np.atleast_1d(axes), windows.items()):
        bands = list(BANDS)
        x = np.arange(len(bands))
        for k, (name, color) in enumerate((("ACS", "#444444"), ("infoUSA all", "#1f5fa8"),
                                           ("infoUSA primary", "#9ab8de"))):
            vals = [src.get(name, {}).get(b, np.nan) for b in bands]
            ax.bar(x + (k - 1) * 0.27, vals, width=0.27, color=color, label=name)
        ax.set_xticks(x, bands)
        ax.set_title(label)
        ax.set_xlabel("age of head of household")
    np.atleast_1d(axes)[0].set_ylabel("share of households")
    np.atleast_1d(axes)[0].legend()
    fig.suptitle("Age of head of household: infoUSA (NC) vs ACS householders (B25007)")
    fig.tight_layout()
    fig.savefig(path_age, dpi=130)
    plt.close(fig)


def main() -> None:
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    FIGURES.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    print("building the family-year panel", flush=True)
    panel = build_panel(con, files)
    years = sorted(files)
    notes = []
    if WINDOW[0] not in files or WINDOW[1] not in files:
        notes.append(f"the files do not cover {WINDOW[0]}-{WINDOW[1]}")

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
            reg, r2, n_app, n_mov = regressions(con)
    summary.insert(0, ["report: NC 2006-2018", f"{REPORT_FAMILIES:,}", f"{REPORT_MEAN:.2f}", f"{REPORT_SD:.2f}",
                       "", "", ""])
    d_all = dists[f"all records {WINDOW[0]}-{WINDOW[1]}"]
    d_prim = dists[f"primary families {WINDOW[0]}-{WINDOW[1]}"]

    # Section 5: age
    print("age", flush=True)
    ages, raw = age_tables(con, panel)
    acs, n_acs = census.state_series(years, [census_fips()], census.AGE_VARS, "acs1_state_age.csv")
    notes += n_acs
    acs_b = acs_band_shares(acs)
    by_year, windows = [], {}
    for _, r in ages.iterrows():
        s = band_shares(r)
        sj = band_shares(r, j_as_missing=True)
        known = sum(r.get(c, 0) for c in AGE_CODES)
        tot = known + r.get("(missing)", 0) + sum(r.get(c, 0) for c in r.index
                                                  if c not in AGE_CODES and c not in ("year", "universe", "(missing)"))
        a = acs_b[acs_b["year"] == r["year"]]
        by_year.append([int(r["year"]), r["universe"], pct(1 - known / tot if tot else np.nan),
                        pct(r.get("J", 0) / known if known else np.nan),
                        pct(s["15-24"]), pct(s["25-34"] + s["35-44"]), pct(s["65+"]), pct(sj["65+"]),
                        pct(a["15-24"].iloc[0]) if len(a) else "", pct((a["25-34"] + a["35-44"]).iloc[0]) if len(a) else "",
                        pct(a["65+"].iloc[0]) if len(a) else ""])
    by_year = pd.DataFrame(by_year, columns=["year", "records", "age code missing", "J (65+ inferred) of known",
                                             "<25", "25-44", "65+", "65+ if J = missing",
                                             "ACS <25", "ACS 25-44", "ACS 65+"]).sort_values(["records", "year"])
    win_rows = []
    for wlabel, (y0, y1) in (("2006-2010", (2007, 2010)), ("2012-2016", (2012, 2016))):
        windows[f"{wlabel} (ours: {y0}-{y1})"] = {}
        for universe in ("all", "primary"):
            sub = ages[(ages["universe"] == universe) & ages["year"].between(y0, y1)]
            s = band_shares(sub.drop(columns=["year", "universe"]).sum())
            windows[f"{wlabel} (ours: {y0}-{y1})"][f"infoUSA {universe}"] = s
        a = acs_b[acs_b["year"].between(y0, y1)]
        if len(a):
            windows[f"{wlabel} (ours: {y0}-{y1})"]["ACS"] = a[list(BANDS)].mean().to_dict()
        w = windows[f"{wlabel} (ours: {y0}-{y1})"]
        win_rows.append([wlabel, pct(REPORT_65[wlabel]["infoUSA"]), pct(w["infoUSA all"]["65+"]),
                         pct(w["infoUSA primary"]["65+"]), pct(REPORT_65[wlabel]["ACS weighted"]),
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
        *([("Notes: " + "; ".join(notes)), ""] if notes else []),
        "## 1. Families and appearances", "",
        "families: distinct FAMILYIDs. appearances: years in the NC files. addresses: distinct street "
        "addresses per FAMILYID (house number, street, ZIP; the report's 'moves' count these, so a family "
        "never seen to move has 1). LOCATIONIDs: distinct Data Axle dwelling IDs. last column: of families "
        "with 2+ street addresses, the share whose LOCATIONID never changed (a hint that some 'moves' are "
        "re-spelled addresses).", "",
        *table(pd.DataFrame(summary, columns=["universe", "families", "mean appearances", "SD",
                                              "mean addresses", "mean LOCATIONIDs",
                                              "2+ addresses, 1 LOCATIONID"])),
        f"### Distribution of appearances, all records {WINDOW[0]}-{WINDOW[1]}", "",
        "Report bars (2006-2018, approximate): " + ", ".join(f"{k}: {pct(v)}" for k, v in REPORT_APPEAR.items())
        + ". moves = addresses - 1; moved: share with 2+ addresses.", "",
        *table(fmt_dist(d_all)),
        f"### Primary families {WINDOW[0]}-{WINDOW[1]}", "",
        *table(fmt_dist(d_prim)),
        "## 1b. The report's regressions", "",
        f"All family records {WINDOW[0]}-{WINDOW[1]}, one row per FAMILYID with complete data. Regressors are "
        "means over the family's years (log income in $1,000 of 2018, CPI-U; own/rent and marital codes "
        "0-9 as numbers; CHILDRENHHCOUNT; LENGTH_OF_RESIDENCE), race from the first known "
        "Ethnicity_Code_1 grouped with config/ethnicity_groups.yaml (base: Asian; the report's race "
        "variable may come from its wru estimates and has Mixed, Native American and Pacific Islander "
        "groups we cannot form), and the head's age code at first appearance (base: under 25; J = 65+ "
        "inferred). Moves: unique street addresses, families seen 4+ times. OLS, classical SEs.", "",
        *table(reg),
        "## 5. Age of the head of household", "",
        "HEAD_HH_AGE_CODE by year: missing share, the share coded J (65+ inferred, which the vendor Q&A "
        "suggests may also mark unknown ages) among known codes, and shares of ACS age bands among known "
        "codes (J counted as 65+), plus 65+ if J is treated as missing. ACS: age of householder, B25007, "
        "1-year.", "",
        *table(by_year),
        "### Report's 5-year windows: share of heads 65+", "",
        *table(pd.DataFrame(win_rows, columns=["window", "report infoUSA (figure)", "ours all", "ours primary",
                                               "report ACS weighted (figure)", "ACS 1-year mean"])),
        "Figures: `output/figures/duke_appearances.png`, `output/figures/duke_age.png`.", "",
    ]))
    print(f"wrote {REPORT}")


def census_fips() -> str:
    from flood_ra import geo
    return geo.STATE_FIPS[STATE]


if __name__ == "__main__":
    main()
