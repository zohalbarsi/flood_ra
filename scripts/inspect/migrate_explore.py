"""Explore MIGRATE for North and South Carolina: moves in, out and within,
2011-2019, and out-migration from the block groups Florence flooded.

MIGRATE: Agostini, Young, Fitzpatrick, Garg and Pierson, "Inferring
fine-grained migration patterns across the United States", NBER Working Paper
34263 (2025), arXiv:2503.20989; data from migrate.tech.cornell.edu. It fits
Infutor address histories to Census totals (its state-to-state flows are
fitted to Census figures, so the new information is below the state level).
Each yearly file holds Origin and Destination block groups (2010 GEOIDs) and
a Flow. The file for year t is read here as moves between year t-1 and t
(to be checked against the MIGRATE documentation).

Not a pipeline step. Run on the server:
    python scripts/inspect/migrate_explore.py [folder]
(folder: the MIGRATE files; default: migrate_raw in config/paths.yaml).
Two passes over each yearly file (all flows; flows touching NC or SC).

- Data checks: rows, total flow, flow from a block group to itself (people
  who did not move, if the matrix includes them), codes that are not block
  groups. Codes are read as text and padded to 12 digits (the files store
  them as numbers, which drops the leading zero of states 01-09).
- NC and SC by year: moves in from other states, out to other states, net,
  moves within the state (other block group; other county), NC <-> SC.
  Rates are shares of the population base: all flows out of the state's
  block groups, staying included.
- Top states of origin and destination.
- Per NC/SC county and block group: staying, moves out and in.
- Flood block groups (step 02's Florence exposure): out-migration rates by
  flood measure, not flooded vs flooded below / above the median.

Writes output/logs/migrate_report.md, output/tables/migrate_*.csv and
output/figures/migrate_flows.png (aggregates by state, county, block group).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import db, geo, paths, settings  # noqa: E402
from flood_ra.report import pct, table  # noqa: E402

STUDY = {"37": "NC", "45": "SC"}
POSTAL = {fips: st for st, fips in geo.STATE_FIPS.items()}
REPORT = paths.LOG_DIR / "migrate_report.md"
TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURES = paths.REPO_ROOT / "output" / "figures"
FLOOD_BG = paths.FLOOD_CLEAN / "flood_bg.parquet"
CITATION = ("MIGRATE: Agostini, Young, Fitzpatrick, Garg and Pierson, \"Inferring fine-grained migration "
            "patterns across the United States\", NBER Working Paper 34263 (2025), arXiv:2503.20989; "
            "data from migrate.tech.cornell.edu.")
IN_STUDY = ", ".join(f"'{s}'" for s in STUDY)


def year_files(root: Path) -> dict[int, Path]:
    """The yearly CSV files (the download unpacks each into a folder of the same name)."""
    files = {}
    for p in sorted(root.rglob("*.csv")):
        y = settings.year_of(p.name)
        if p.is_file() and y is not None:
            if y in files:
                sys.exit(f"two files for {y}: {files[y]} and {p}")
            files[y] = p
    return files


def flows(f: Path) -> str:
    """One year's flows with 12-digit block-group codes (NULL if not a block group)."""
    def code(col: str) -> str:
        return f"CASE WHEN regexp_full_match(trim({col}), '[0-9]{{11,12}}') THEN lpad(trim({col}), 12, '0') END"
    return (f"(SELECT {code('Origin')} AS o, {code('Destination')} AS d, TRY_CAST(Flow AS DOUBLE) AS flow "
            f"FROM read_csv('{f.as_posix()}', header=true, "
            "types={'Origin': 'VARCHAR', 'Destination': 'VARCHAR', 'Flow': 'VARCHAR'}))")


def one_year(con, year: int, f: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """State-pair totals (all flows) and NC/SC block-group totals for one year."""
    states = con.sql(f"""
        SELECT left(o, 2) AS origin, left(d, 2) AS destination, count(*) AS rows,
               count(*) FILTER (WHERE o = d) AS rows_same_bg, sum(flow) AS flow,
               sum(flow) FILTER (WHERE o = d) AS flow_same_bg,
               count(*) FILTER (WHERE flow < 1) AS rows_below_1, min(flow) AS min_flow, max(flow) AS max_flow
        FROM {flows(f)} GROUP BY ALL""").df().assign(year=year)
    con.sql(f"""CREATE OR REPLACE TEMP TABLE r AS SELECT * FROM {flows(f)}
                WHERE left(o, 2) IN ({IN_STUDY}) OR left(d, 2) IN ({IN_STUDY})""")
    bg = con.sql(f"""
        WITH out_ AS (
            SELECT o AS bg, sum(flow) FILTER (WHERE o = d) AS stayed,
                   sum(flow) FILTER (WHERE o != d) AS moved_out,
                   sum(flow) FILTER (WHERE o != d AND left(d, 5) = left(o, 5)) AS out_same_county,
                   sum(flow) FILTER (WHERE left(d, 5) != left(o, 5) AND left(d, 2) = left(o, 2)) AS out_other_county,
                   sum(flow) FILTER (WHERE left(d, 2) != left(o, 2)) AS out_other_state
            FROM r WHERE left(o, 2) IN ({IN_STUDY}) GROUP BY o),
        in_ AS (
            SELECT d AS bg, sum(flow) FILTER (WHERE o != d) AS moved_in,
                   sum(flow) FILTER (WHERE o != d AND left(o, 5) = left(d, 5)) AS in_same_county,
                   sum(flow) FILTER (WHERE left(o, 5) != left(d, 5) AND left(o, 2) = left(d, 2)) AS in_other_county,
                   sum(flow) FILTER (WHERE left(o, 2) != left(d, 2)) AS in_other_state
            FROM r WHERE left(d, 2) IN ({IN_STUDY}) GROUP BY d)
        SELECT {year} AS year, bg, out_.* EXCLUDE (bg), in_.* EXCLUDE (bg)
        FROM out_ FULL JOIN in_ USING (bg)""").df()
    con.sql("DROP TABLE r")
    num = [c for c in bg.columns if c not in ("year", "bg")]
    bg[num] = bg[num].fillna(0.0)
    bg["population"] = bg["stayed"] + bg["moved_out"]  # everyone who started the year there
    return states, bg


def state_summary(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (year, fips), _ in states[states["origin"].isin(STUDY)].groupby(["year", "origin"]):
        s = states[states["year"] == year]
        out_ = s[s["origin"] == fips]
        in_ = s[(s["destination"] == fips) & (s["origin"] != fips)]
        same = out_[out_["destination"] == fips]
        other = [f for f in STUDY if f != fips][0]
        rows.append({
            "year": year, "state": STUDY[fips],
            "population": out_["flow"].sum(),
            "stayed_same_bg": same["flow_same_bg"].sum(),
            "moved_within_state": (same["flow"] - same["flow_same_bg"].fillna(0)).sum(),
            "out_to_other_states": out_[out_["destination"] != fips]["flow"].sum(),
            "in_from_other_states": in_["flow"].sum(),
            f"to_{STUDY[other]}": out_[out_["destination"] == other]["flow"].sum(),
            f"from_{STUDY[other]}": in_[in_["origin"] == other]["flow"].sum(),
        })
    df = pd.DataFrame(rows)
    df["net_from_other_states"] = df["in_from_other_states"] - df["out_to_other_states"]
    return df.sort_values(["state", "year"])


def flood_groups(bg: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Out-migration rates of the flood block groups, by measure and group."""
    notes = []
    if not FLOOD_BG.exists():
        return pd.DataFrame(), [f"no flood groups: {FLOOD_BG} not found (run step 02)"]
    fl = pd.read_parquet(FLOOD_BG)
    measures = [c for c in fl.columns if c.startswith("bg_pct_flooded_")]
    nc = bg[bg["bg"].str[:2] == "37"]
    covered = nc["bg"].isin(set(fl["bg_geoid"]))
    found = fl["bg_geoid"].isin(set(nc["bg"]))
    notes.append(f"flood block groups found in MIGRATE: {found.sum():,} of {len(fl):,}")
    rows = []
    for m in measures:
        v = fl[["bg_geoid", m]].dropna()
        cut = v.loc[v[m] > 0, m].median()
        group = pd.Series("not flooded", index=v.index)
        group[v[m] > 0] = "flooded, below median"
        group[v[m] >= cut] = "flooded, median or more"
        g = dict(zip(v["bg_geoid"], group))
        d = nc.assign(group=nc["bg"].map(g))
        d.loc[~covered, "group"] = "rest of NC"
        for (year, grp), x in d.dropna(subset=["group"]).groupby(["year", "group"]):
            pop = x["population"].sum()
            rows.append({"measure": m.replace("bg_pct_flooded_", ""), "group": grp, "year": year,
                         "block_groups": len(x), "population": pop,
                         "out_rate": x["moved_out"].sum() / pop if pop else None,
                         "out_of_county_rate": (x["out_other_county"] + x["out_other_state"]).sum() / pop if pop else None,
                         "out_of_state_rate": x["out_other_state"].sum() / pop if pop else None,
                         "in_rate": x["moved_in"].sum() / pop if pop else None})
    return pd.DataFrame(rows), notes


def plot(summary: pd.DataFrame, groups: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"NC": "#1f5fa8", "SC": "#c8611c"}
    gcolors = {"not flooded": "#888888", "flooded, below median": "#7fb2e5",
               "flooded, median or more": "#1f5fa8", "rest of NC": "#c8611c"}
    measures = sorted(groups["measure"].unique()) if len(groups) else []
    ncol = max(3, len(measures))
    fig, axes = plt.subplots(2, ncol, figsize=(4.6 * ncol, 8.4), squeeze=False)
    pctf = matplotlib.ticker.PercentFormatter(1.0)
    num = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    for st, d in summary.groupby("state"):
        axes[0, 0].plot(d["year"], d["in_from_other_states"], "-o", ms=3, color=colors[st], label=f"{st} in")
        axes[0, 0].plot(d["year"], d["out_to_other_states"], "--o", ms=3, color=colors[st], label=f"{st} out")
        axes[0, 1].plot(d["year"], d["net_from_other_states"], "-o", ms=3, color=colors[st], label=st)
        axes[0, 2].plot(d["year"], d["moved_within_state"] / d["population"], "-o", ms=3, color=colors[st],
                        label=st)
    axes[0, 0].set_title("People moving in from / out to other states")
    axes[0, 1].set_title("Net moves from other states")
    axes[0, 2].set_title("Moved to another block group in the state")
    axes[0, 0].yaxis.set_major_formatter(num)
    axes[0, 1].yaxis.set_major_formatter(num)
    axes[0, 1].axhline(0, color="black", lw=0.6)
    axes[0, 2].yaxis.set_major_formatter(pctf)
    for ax in axes[0, 3:]:
        ax.set_visible(False)
    for ax, m in zip(axes[1], measures):
        gm = groups[groups["measure"] == m]
        for grp in gcolors:
            d = gm[gm["group"] == grp].sort_values("year")
            if len(d):
                ax.plot(d["year"], d["out_of_county_rate"], "-o", ms=3, color=gcolors[grp], label=grp)
        ax.set_title(f"Left the county, flood measure {m}")
        ax.yaxis.set_major_formatter(pctf)
    for ax in axes[1, len(measures):]:
        ax.set_visible(False)
    for ax in axes.flat:
        if ax.get_visible():
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            ax.axvline(2018.7, color="grey", lw=0.8, ls=":")
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8, loc="best")
    fig.suptitle("MIGRATE, NC and SC (file year t = moves from t-1 to t). Dotted line: Hurricane Florence",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else paths.MIGRATE_RAW
    if root is None:
        sys.exit("give the MIGRATE folder, or set migrate_raw in config/paths.yaml")
    paths.require(root)
    files = year_files(root)
    if not files:
        sys.exit(f"no yearly .csv files in {root}")
    for d in (TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    states, bgs = [], []
    for year, f in files.items():
        s, b = one_year(con, year, f)
        states.append(s)
        bgs.append(b)
        print(f"{year}: {s['rows'].sum():,} flows read", flush=True)
    states, bg = pd.concat(states, ignore_index=True), pd.concat(bgs, ignore_index=True)

    checks = states.groupby("year").agg(
        rows=("rows", "sum"), rows_same_bg=("rows_same_bg", "sum"), flow=("flow", "sum"),
        flow_same_bg=("flow_same_bg", "sum"), rows_below_1=("rows_below_1", "sum"),
        min_flow=("min_flow", "min"), max_flow=("max_flow", "max")).reset_index()
    bad = states[states["origin"].isna() | states["destination"].isna()].groupby("year")["rows"].sum()
    checks["rows_bad_code"] = checks["year"].map(bad).fillna(0).astype(int)
    summary = state_summary(states)
    pairs = states[(states["origin"].isin(STUDY) | states["destination"].isin(STUDY))
                   & (states["origin"] != states["destination"])].copy()
    pairs["origin"] = pairs["origin"].map(POSTAL).fillna(pairs["origin"])
    pairs["destination"] = pairs["destination"].map(POSTAL).fillna(pairs["destination"])
    pairs = pairs[["year", "origin", "destination", "flow"]].sort_values(["year", "origin", "destination"])
    bg["county"] = bg["bg"].str[:5]
    county = bg.groupby(["year", "county"])[[c for c in bg.columns if c not in ("year", "bg", "county")]] \
        .sum().reset_index()
    county["state"] = county["county"].str[:2].map(STUDY)
    county["moved_out_of_county"] = county["out_other_county"] + county["out_other_state"]
    county["moved_into_county"] = county["in_other_county"] + county["in_other_state"]
    groups, notes = flood_groups(bg)

    checks.to_csv(TABLES / "migrate_checks.csv", index=False)
    summary.to_csv(TABLES / "migrate_state_summary.csv", index=False)
    pairs.to_csv(TABLES / "migrate_state_pairs.csv", index=False)
    county.to_csv(TABLES / "migrate_county.csv", index=False)
    bg.drop(columns=["county"]).round(3).to_csv(TABLES / "migrate_bg.csv", index=False)
    groups.to_csv(TABLES / "migrate_flood_groups.csv", index=False)
    plot(summary, groups, FIGURES / "migrate_flows.png")

    # report tables
    millions = lambda v: f"{v / 1e6:,.1f}M"  # noqa: E731
    chk = pd.DataFrame({
        "year": checks["year"], "flows (rows)": checks["rows"].map(millions),
        "total flow": checks["flow"].map(millions),
        "same block group": (checks["flow_same_bg"] / checks["flow"]).map(pct),
        "rows with flow < 1": (checks["rows_below_1"] / checks["rows"]).map(pct),
        "min flow": checks["min_flow"].map(lambda v: f"{v:.3g}"),
        "max flow": checks["max_flow"].map(lambda v: f"{v:,.0f}"),
        "codes not block groups": checks["rows_bad_code"].map("{:,}".format)})
    stayers = (checks["flow_same_bg"] / checks["flow"]).median() > 0.5
    base = "population" if stayers else "total flow out (movers only)"
    fmt_n = lambda v: f"{v:,.0f}"  # noqa: E731
    summ = pd.DataFrame({
        "year": summary["year"], "state": summary["state"], base: summary["population"].map(fmt_n),
        "moved within state": (summary["moved_within_state"] / summary["population"]).map(pct),
        "out to other states": summary["out_to_other_states"].map(fmt_n),
        "in from other states": summary["in_from_other_states"].map(fmt_n),
        "net": summary["net_from_other_states"].map(fmt_n),
        "out rate": (summary["out_to_other_states"] / summary["population"]).map(pct),
        "in rate": (summary["in_from_other_states"] / summary["population"]).map(pct)})
    (a, b), (sa, sb) = list(STUDY), list(STUDY.values())
    ncsc = pd.DataFrame({"year": sorted(files)})
    for o, d, label in ((a, b, f"{sa} to {sb}"), (b, a, f"{sb} to {sa}")):
        x = states[(states["origin"] == o) & (states["destination"] == d)].groupby("year")["flow"].sum()
        ncsc[label] = ncsc["year"].map(x).fillna(0).map(lambda v: f"{v:,.0f}")
    top = pd.DataFrame({"rank": range(1, 11)})
    moves = states[states["origin"] != states["destination"]]
    for fips, st in STUDY.items():
        for kind, rows, other in (("from", moves["destination"] == fips, "origin"),
                                  ("to", moves["origin"] == fips, "destination")):
            t = moves[rows].groupby(other)["flow"].sum().sort_values(ascending=False)
            head = (t / t.sum()).head(10)
            top[f"{st} {kind}"] = pd.Series([POSTAL.get(k, k) for k in head.index], dtype=object).reindex(range(10)).values
            top["share" + " " * len(top.columns)] = pd.Series([pct(v) for v in head.values],
                                                              dtype=object).reindex(range(10)).values
    top.columns = [c.strip() for c in top.columns]
    top = top.fillna("")
    fc = county.copy()
    fc["group"] = fc["state"]
    if FLOOD_BG.exists():
        flood_counties = set(pd.read_parquet(FLOOD_BG)["bg_geoid"].str[:5])
        fc.loc[fc["county"].isin(flood_counties), "group"] = "NC flood counties"
        fc.loc[(fc["state"] == "NC") & ~fc["county"].isin(flood_counties), "group"] = "rest of NC"
    cg = fc.groupby(["year", "group"])[["population", "moved_out_of_county", "out_other_state", "moved_into_county"]] \
        .sum().reset_index()
    order = [g for g in ("NC flood counties", "rest of NC", "NC", "SC") if g in set(cg["group"])]
    cty = {}
    for label, num_ in (("left", "moved_out_of_county"), ("came in", "moved_into_county")):
        w = cg.assign(v=(cg[num_] / cg["population"]).map(pct)).pivot_table(
            index="year", columns="group", values="v", aggfunc="first")
        cty[label] = w[[g for g in order if g in w.columns]].reset_index()
        cty[label].columns.name = None
    flood = pd.DataFrame()
    if len(groups):
        g = groups.copy()
        g["left the county"] = g["out_of_county_rate"].map(pct)
        flood = g.pivot_table(index=["measure", "year"], columns="group", values="left the county",
                              aggfunc="first")
        flood = flood[[c for c in ("not flooded", "flooded, below median", "flooded, median or more",
                                   "rest of NC") if c in flood.columns]].fillna("").reset_index()
        flood.columns.name = None
        sizes = groups[groups["year"] == groups["year"].max()].pivot_table(
            index="measure", columns="group", values="block_groups", aggfunc="first")
        notes.append("block groups per group (" + str(groups["year"].max()) + "): " + "; ".join(
            f"{m}: " + ", ".join(f"{k} {int(v):,}" for k, v in r.dropna().items()) for m, r in sizes.iterrows()))

    REPORT.write_text("\n".join([
        "# MIGRATE: moves in, out and within NC and SC (aggregates)", "",
        f"Source: {CITATION} Files: {', '.join(map(str, files))}. The file for year t is read as moves "
        "between year t-1 and year t (check against the MIGRATE documentation). Block-group codes are "
        "read as text and padded to 12 digits. Figure: `output/figures/migrate_flows.png`; tables "
        "(state, county and block group, by year): `output/tables/migrate_*.csv`.", "",
        *([("Notes: " + "; ".join(notes)), ""] if notes else []),
        "## Data checks (all flows in the US)", "",
        "same block group: share of the total flow from a block group to itself. If it holds most of the "
        "flow, the matrix includes people who did not move and the total is close to the US population "
        f"(about 310-330M in 2010-2019); otherwise it holds movers only. Here: "
        f"{'it includes people who did not move' if stayers else 'movers only'}, so rates below are "
        f"shares of the {base}.", "",
        *table(chk),
        "## NC and SC by year", "",
        f"{base}: all flows out of the state's block groups{', staying included' if stayers else ''}. "
        "moved within state: to another block group in the same state, as a share of it. out / in: people "
        "moving to / from other states; net = in - out.", "",
        *table(summ),
        "### Between NC and SC", "",
        *table(ncsc),
        f"### Top 10 states people come from and go to, {min(files)}-{max(files)}", "",
        "Shares of all moves into (from) or out of (to) each state, from or to other states.", "",
        *table(top),
        "## Counties: leaving and entering, by year", "",
        "Shares of the county population base (people who started the year in the county). Groups: the "
        "34 NC counties in the flood data, the rest of NC, and SC.", "",
        "### Left the county", "", *table(cty["left"]),
        "### Came into the county", "", *table(cty["came in"]),
        "## Block groups by Florence flood exposure (NC flood counties)", "",
        "Share of people who left their county during the year, by flood measure (step 02, block-group "
        "share flooded): not flooded (0), flooded below the median of flooded block groups, flooded at or "
        "above it; 'rest of NC' is every NC block group outside the flood data. If Florence displaced "
        "people, the flooded groups should stand out in 2019 (moves 2018-2019).", "",
        *(table(flood) if len(flood) else ["(no flood groups)", ""]),
    ]))
    print(f"wrote {REPORT} ({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
