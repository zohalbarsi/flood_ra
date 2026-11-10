"""The 2017 NC/SC households, followed to 2024: counts, demographics, attrition.

Cohort: households that are a primary family in NC or SC in 2017 (household
panel, step 08). The group is fixed: every household has a row in every year,
found or not. Found: a record anywhere in the US files that year (same
FAMILYID, or one it continues under).

Run on the server after step 08:
    python scripts/inspect/cohort_panel.py [base year]
Writes derived/panel/cohort_<year>.parquet (server only: one row per household
and year) and, with counts and shares only, output/logs/cohort_<year>.md,
output/tables/cohort_<year>_by_year.csv, cohort_<year>_attrition.csv and
output/figures/cohort_<year>.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import db, panel, paths, settings  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

BASE = int(sys.argv[1]) if len(sys.argv) > 1 else 2017
TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURE = paths.REPO_ROOT / "output" / "figures" / f"cohort_{BASE}.png"
REPORT = paths.LOG_DIR / f"cohort_{BASE}.md"
SLICES = 16  # households are processed in slices so each sort fits in memory
FOUND = "status IN ('NC/SC', 'other state')"
AGES = ["under 35", "35-44", "45-54", "55-64", "65 and over"]
# base-year characteristics the attrition table splits by: label -> column (without the _<year> suffix)
GROUPS = {"state": "state", "tenure": "tenure", "race": "race", "income": "income_quartile",
          "children": "children", "head's age": "head_age"}


def age(c: str) -> str:  # HEAD_HH_AGE_CODE: A <25, B 25-29, ..., I 60-64, J-M 65+ (README codebook)
    return (f"CASE WHEN {c} IN ('A', 'B', 'C') THEN 'under 35' WHEN {c} IN ('D', 'E') THEN '35-44' "
            f"WHEN {c} IN ('F', 'G') THEN '45-54' WHEN {c} IN ('H', 'I') THEN '55-64' "
            f"WHEN {c} IN ('J', 'K', 'L', 'M') THEN '65 and over' ELSE 'unknown' END")


def race(c: str) -> str:  # broad group of the first person's ethnicity code (ethnicity.py)
    return (f"CASE WHEN {c} IN ('white', 'black', 'hispanic', 'asian') THEN {c} "
            f"WHEN {c} IS NULL THEN 'unknown' ELSE 'other' END")


def children(c: str) -> str:
    return f"CASE {c} WHEN 1 THEN 'with children' WHEN 0 THEN 'no children' ELSE 'unknown' END"


def panel_file(year: int) -> str:
    return (panel.DIR / f"panel_{year}.parquet").as_posix()


def build(con, years: list[int], out: Path) -> list[float]:
    """The household file: one row per cohort household and year, sorted by household.
    Returns the base-year income quartile cut-offs."""
    work = panel.DIR / "cohort_work"
    work.mkdir(parents=True, exist_ok=True)
    base = (work / "base.parquet").as_posix()
    con.sql(f"""COPY (SELECT hhid, state, county, tenure, income, {children('kids')} AS children,
                             {age('head_age')} AS head_age, {race('eth_broad')} AS race
                      FROM read_parquet('{panel_file(BASE)}') WHERE in_study AND prim)
                TO '{base}' (FORMAT parquet)""")
    q = con.sql(f"SELECT quantile_cont(income, [0.25, 0.5, 0.75]) FROM read_parquet('{base}')").fetchall()[0][0]
    quartile = (f"CASE WHEN b.income IS NULL THEN 'unknown' WHEN b.income <= {q[0]} THEN '1 (lowest)' "
                f"WHEN b.income <= {q[1]} THEN '2' WHEN b.income <= {q[2]} THEN '3' ELSE '4 (highest)' END")
    files = "read_parquet([" + ", ".join(f"'{panel_file(y)}'" for y in years) + "])"
    found = "f.hhid IS NOT NULL"
    parts = []
    for k in range(SLICES):
        part = (work / f"part_{k}.parquet").as_posix()
        con.sql(f"""COPY (
            WITH b AS (SELECT * FROM read_parquet('{base}') WHERE hash(hhid) % {SLICES} = {k}),
                 f AS MATERIALIZED (SELECT hhid, year, fid, state, county, in_study, moved, tenure, income,
                                           kids, head_age, eth_broad
                       FROM {files} WHERE hash(hhid) % {SLICES} = {k} AND hhid IN (SELECT hhid FROM b)),
                 l AS (SELECT hhid, max(year) AS last_seen FROM f GROUP BY hhid)
            SELECT b.hhid, g.year,
                   CASE WHEN {found} THEN (CASE WHEN f.in_study THEN 'NC/SC' ELSE 'other state' END)
                        WHEN g.year < l.last_seen THEN 'missing, back later' ELSE 'gone for good' END AS status,
                   f.fid, f.state, f.county, f.moved, f.tenure, f.income,
                   CASE WHEN {found} THEN {children('f.kids')} END AS children,
                   CASE WHEN {found} THEN {age('f.head_age')} END AS head_age,
                   CASE WHEN {found} THEN {race('f.eth_broad')} END AS race,
                   b.state AS state_{BASE}, b.county AS county_{BASE}, b.tenure AS tenure_{BASE},
                   b.income AS income_{BASE}, {quartile} AS income_quartile_{BASE}, b.children AS children_{BASE},
                   b.head_age AS head_age_{BASE}, b.race AS race_{BASE}, l.last_seen
            FROM b CROSS JOIN (SELECT unnest(range({years[0]}, {years[-1] + 1})) AS year) g
                 JOIN l ON l.hhid = b.hhid
                 LEFT JOIN f ON f.hhid = b.hhid AND f.year = g.year
            ORDER BY b.hhid, g.year
        ) TO '{part}' (FORMAT parquet, COMPRESSION zstd)""")
        parts.append(part)
        print(f"  households: slice {k + 1} of {SLICES}", flush=True)
    con.sql("COPY (SELECT * FROM read_parquet([" + ", ".join(f"'{x}'" for x in parts) + "])) "
            f"TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    for x in [*parts, base]:
        Path(x).unlink()
    work.rmdir()
    return q


def by_year(con, cohort: str) -> pd.DataFrame:
    """Counts per year: where the cohort is, and the demographics of the households found."""
    return con.sql(f"""
        SELECT year, count(*) AS cohort, count(*) FILTER (WHERE {FOUND}) AS found,
               count(*) FILTER (WHERE status = 'NC/SC') AS in_nc_sc,
               count(*) FILTER (WHERE status = 'other state') AS in_other_states,
               count(*) FILTER (WHERE status = 'missing, back later') AS missing_back_later,
               count(*) FILTER (WHERE status = 'gone for good') AS gone_for_good,
               count(*) FILTER (WHERE fid != hhid) AS new_familyid,
               count(moved) AS moved_known, count(*) FILTER (WHERE moved) AS moved,
               count(*) FILTER (WHERE tenure = 'owner') AS owners, count(*) FILTER (WHERE tenure = 'renter') AS renters,
               count(*) FILTER (WHERE tenure = 'unknown') AS tenure_unknown,
               count(*) FILTER (WHERE children = 'with children') AS with_children,
               count(*) FILTER (WHERE children IN ('with children', 'no children')) AS children_known,
               median(income) AS median_income,
               count(*) FILTER (WHERE race = 'white') AS white, count(*) FILTER (WHERE race = 'black') AS black,
               count(*) FILTER (WHERE race = 'hispanic') AS hispanic, count(*) FILTER (WHERE race = 'asian') AS asian,
               count(*) FILTER (WHERE race != 'unknown') AS race_known,
               count(*) FILTER (WHERE head_age = '65 and over') AS head_65_plus,
               count(*) FILTER (WHERE head_age != 'unknown') AS age_known
        FROM {cohort} GROUP BY year ORDER BY year""").df()


def attrition(con, cohort: str, years: list[int], n: int) -> pd.DataFrame:
    """Per base-year group: households, share of the cohort, and how many are found each later year."""
    keys = [f"{c}_{BASE}" for c in GROUPS.values()]
    found = ", ".join(f"count(*) FILTER (WHERE year = {y} AND {FOUND}) AS found_{y}" for y in years[1:])
    att = con.sql(f"""SELECT {', '.join(keys)}, count(*) FILTER (WHERE year = {BASE}) AS households, {found},
                             count(*) FILTER (WHERE year = {BASE} AND last_seen = {BASE}) AS never_after_{BASE}
                      FROM {cohort} GROUP BY GROUPING SETS ({', '.join(f'({c})' for c in keys)})""").df()
    att.insert(0, "group", "")
    att.insert(1, "value", "")
    for label, col in zip(GROUPS, keys):
        has = att[col].notna()
        att.loc[has, "group"], att.loc[has, "value"] = label, att.loc[has, col]
    att.insert(3, "share_of_cohort", (att["households"] / n).round(4))
    order = {label: i for i, label in enumerate(GROUPS)}
    value_order = {v: i for i, v in enumerate(AGES)}  # age bands in age order, other values alphabetically
    att["_g"], att["_v"] = att["group"].map(order), att["value"].map(lambda v: value_order.get(v, 99))
    return att.sort_values(["_g", "_v", "value"]).drop(columns=[*keys, "_g", "_v"]).reset_index(drop=True)


def plot(d: pd.DataFrame, att: pd.DataFrame, years: list[int], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, ink2, grid, axis, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#ffffff"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": axis, "axes.labelcolor": ink2, "text.color": ink,
                         "xtick.color": ink2, "ytick.color": ink2, "axes.titlesize": 11, "axes.titlelocation": "left"})
    percent = matplotlib.ticker.PercentFormatter(1.0, decimals=0)
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), layout="constrained")

    # 1. where the cohort is each year: blue/orange found, greys not found
    ax = axes[0, 0]
    stack = [("in NC/SC", "in_nc_sc", "#2a78d6", "white"), ("in another state", "in_other_states", "#eb6834", ink),
             ("missing, back later", "missing_back_later", "#b9b8ae", ink),
             ("gone for good", "gone_for_good", "#6f6e69", "white")]
    bottom = np.zeros(len(d))
    for label, col, color, text in stack:
        share = (d[col] / d["cohort"]).to_numpy()
        ax.bar(d["year"], share, bottom=bottom, width=0.72, color=color, edgecolor=surface, linewidth=1.2,
               label=label)
        if share[-1] >= 0.06:  # label the last year's segments that fit
            ax.text(d["year"].iloc[-1], bottom[-1] + share[-1] / 2, f"{share[-1]:.0%}", ha="center", va="center",
                    color=text, fontsize=9)
        bottom += share
    ax.set_ylim(0, 1)
    ax.set_title(f"Where the {BASE} households are")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2, frameon=False, fontsize=9)

    # 2-4. share of each base-year group found each year
    panels = [(axes[0, 1], "tenure", [("owner", "#2a78d6"), ("renter", "#eb6834"), ("unknown", "#1baf7a")]),
              (axes[1, 0], "head's age", list(zip(AGES, ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]))),
              (axes[1, 1], "race", [("white", "#2a78d6"), ("black", "#eb6834"), ("hispanic", "#1baf7a"),
                                    ("asian", "#eda100")])]
    lowest, ends = 1.0, {}
    for ax, group, series in panels:
        ends[group] = []
        for value, color in series:
            r = att[(att["group"] == group) & (att["value"] == value)]
            if r.empty or r["households"].iloc[0] == 0:
                continue
            r = r.iloc[0]
            ys = [1.0] + [r[f"found_{y}"] / r["households"] for y in years[1:]]
            lowest = min(lowest, *ys)
            ax.plot(years, ys, color=color, lw=1.6, marker="o", ms=4, label=value, zorder=3)
            ends[group].append((value, ys[-1]))
        ax.set_title(f"Share found, by {BASE} {group}" + (" (first person)" if group == "race" else ""))
    lo = max(0, lowest - 0.05)
    for ax, group, _ in panels:  # same scale in the three panels
        ax.set_ylim(lo, 1.02)
        ax.set_xlim(years[0] - 0.4, years[-1] + 1.3)
        ax.legend(loc="best", frameon=False, fontsize=9)
        if len(ends[group]) <= 4:  # direct labels at the line ends, spread so they don't overlap
            gap, placed = 0.045 * (1.02 - lo), []
            for value, y in sorted(ends[group], key=lambda e: e[1]):
                placed.append(max(y, placed[-1] + gap) if placed else y)
                ax.text(years[-1] + 0.2, placed[-1], value, va="center", fontsize=9, color=ink2)
    for ax in axes.flat:
        ax.yaxis.set_major_formatter(percent)
        ax.set_xticks(years)
        ax.grid(axis="y", color=grid, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(length=0)
    fig.suptitle(f"Households in NC or SC in {BASE} (primary families, n = {d['cohort'].iloc[0]:,}), "
                 f"followed to {years[-1]}\nFound: a record anywhere in the US files that year",
                 x=0.02, ha="left", fontsize=12)
    fig.savefig(path, dpi=150, facecolor=surface)
    plt.close(fig)


def main() -> None:
    last = settings.LAST_YEAR or 2024
    years = list(range(BASE, last + 1))
    absent = [y for y in years if not Path(panel_file(y)).exists()]
    if absent:
        sys.exit(f"no panel file for {', '.join(map(str, absent))} in {panel.DIR}; run step 08 first")
    for folder in (TABLES, FIGURE.parent):
        folder.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    con.sql("SET preserve_insertion_order = true")  # keep each household's rows together, in year order
    out = panel.DIR / f"cohort_{BASE}.parquet"
    q = build(con, years, out)
    cohort = f"read_parquet('{out.as_posix()}')"
    n = con.sql(f"SELECT count(*) FROM {cohort} WHERE year = {BASE}").fetchall()[0][0]
    d = by_year(con, cohort)
    d.to_csv(TABLES / f"cohort_{BASE}_by_year.csv", index=False)
    att = attrition(con, cohort, years, n)
    att.to_csv(TABLES / f"cohort_{BASE}_attrition.csv", index=False)
    plot(d, att, years, FIGURE)

    share = lambda a, b: (a / b.where(b > 0)).map(pct)  # noqa: E731
    count = lambda s: s.map("{:,}".format)  # noqa: E731
    composition = pd.DataFrame({"group": att["group"], "value": att["value"], "households": count(att["households"]),
                                "% of cohort": att["share_of_cohort"].map(pct)})
    counts = pd.DataFrame({
        "year": d["year"], "found": count(d["found"]), "in NC/SC": count(d["in_nc_sc"]),
        "other states": count(d["in_other_states"]), "missing, back later": count(d["missing_back_later"]),
        "gone for good": count(d["gone_for_good"]), "found under a new FAMILYID": count(d["new_familyid"])})
    shares = pd.DataFrame({
        "year": d["year"], "found": share(d["found"], d["cohort"]), "in NC/SC": share(d["in_nc_sc"], d["cohort"]),
        "other states": share(d["in_other_states"], d["cohort"]),
        "missing, back later": share(d["missing_back_later"], d["cohort"]),
        "gone for good": share(d["gone_for_good"], d["cohort"]),
        "moved since last year": share(d["moved"], d["moved_known"])})
    demo = pd.DataFrame({
        "year": d["year"], "owner": share(d["owners"], d["found"]), "renter": share(d["renters"], d["found"]),
        "tenure unknown": share(d["tenure_unknown"], d["found"]),
        "with children": share(d["with_children"], d["children_known"]),
        "median income": d["median_income"].map(lambda v: "" if pd.isna(v) else f"{v:,.0f}"),
        "White": share(d["white"], d["race_known"]), "Black": share(d["black"], d["race_known"]),
        "Hispanic": share(d["hispanic"], d["race_known"]), "Asian": share(d["asian"], d["race_known"]),
        "head 65+": share(d["head_65_plus"], d["age_known"])})
    found = pd.DataFrame({"group": att["group"], "value": att["value"]})
    for y in years[1:]:
        found[str(y)] = share(att[f"found_{y}"], att["households"])
    found[f"never found after {BASE}"] = share(att[f"never_after_{BASE}"], att["households"])
    REPORT.write_text("\n".join([
        f"# The {BASE} NC/SC households, followed to {years[-1]} (counts and shares only)", "",
        f"Cohort: the {n:,} households that are a primary family in NC or SC in {BASE} (household panel, "
        "step 08). The group is fixed: shares are of the whole cohort unless stated. Found: a record anywhere "
        "in the US files that year (same FAMILYID, or one the household continues under). Missing, back "
        "later: not found that year but found in a later one. Gone for good: not found that year or any later "
        f"year up to {years[-1]} (so in {years[-1]} every household not found counts as gone). A household "
        "whose adults join another household, or split up, is not found from then on (step 08's links).", "",
        f"Figure: `output/figures/cohort_{BASE}.png`. Tables with all counts: "
        f"`output/tables/cohort_{BASE}_by_year.csv`, `cohort_{BASE}_attrition.csv`.", "",
        f"## The {BASE} households", "",
        f"Median {BASE} income ${q[1]:,.0f}; income quartile cut-offs ${q[0]:,.0f}, ${q[1]:,.0f}, ${q[2]:,.0f}.", "",
        *table(composition),
        "## Counts and attrition", "",
        *table(counts),
        f"Shares of the {n:,} households; moved since last year: among households found that year and the "
        "year before, the share at a new address.", "",
        *table(shares),
        "## Demographics of the households found each year", "",
        "Owner, renter, tenure unknown: OWNER_RENTER_STATUS 7-9, 0-3 and the rest, of households found; with "
        "children: among households with a known CHILDREN_IND; race of the first person (ethnicity.py) among "
        "households with a known code; head 65+: among households with a known HEAD_HH_AGE_CODE. These "
        "change with who stays in the files (attrition is not random, see below) and with Data Axle's "
        "recoding (tenure in 2019).", "",
        *table(demo),
        f"## Attrition by {BASE} characteristics", "",
        f"Share of each {BASE} group found in each year; last column: never found again after {BASE}.", "",
        *table(found),
        "## The household file", "",
        f"`derived/panel/cohort_{BASE}.parquet` on the server, one row per household and year "
        f"({n * len(years):,} rows), sorted by household and year. Columns:", "",
        "- `hhid`: household (its first FAMILYID in the panel, kept when it continues under a new one); `year`",
        "- `status`: NC/SC, other state, missing, back later, gone for good",
        "- `fid`: FAMILYID of that year's record; `state`, `county` (5-digit FIPS): where it is that year",
        "- `moved`: at a new address since the year before (empty if not found the year before)",
        "- `tenure` (owner, renter, unknown), `income` (dollars, FIND_DIV_1000 x 1000), `children`, "
        "`head_age` (band), `race` (first person): that year's record",
        f"- the same with `_{BASE}`: the household in {BASE}; `income_quartile_{BASE}`; `last_seen`: the last "
        "year it is found",
        "", "Columns from that year's record are empty in years the household is not found.", "",
    ]))
    print(f"wrote {REPORT}, {FIGURE.name} and {out}")


if __name__ == "__main__":
    main()
