"""Step 6: demographic trends of infoUSA households, NC vs SC, against Census
benchmarks; and maps of race and homeownership by census tract.

Unit: households = primary families (PRIMARY_FAMILY_IND = 1). Variables
(Data Axle dictionary):
- owners / renters: OWNER_RENTER_STATUS 7-9 owner, 0-3 renter, 4-6 unknown.
  Plotted owner share: codes 7-9 among households coded 0-9, so the unknowns
  count as renters (the Duke DPRC report's second measure, which is closer to
  ACS). Tables also give owners among known codes (0-3, 7-9). Census: ACS B25003.
- children: CHILDREN_IND = 1 and the mean of CHILDRENHHCOUNT. Census: ACS
  B11005 (households with someone under 18) and B09001 (people under 18 in
  households) per household.
- income: FIND_DIV_1000 ($ thousands, top-coded at 500). Census: ACS B19013
  median household income (nominal dollars, like infoUSA).
- wealth: WEALTH_FINDER_SCORE ($ thousands). No state Census benchmark exists.
- home value: ESTMTD_HOME_VAL_DIV_1000 of likely owners. Census: ACS B25077.
- race / ethnicity: Ethnicity_Code_1 (the first person; 00 or blank =
  missing), grouped into White, Black, Hispanic, Asian and other with
  config/ethnicity_groups.yaml if it exists. Otherwise the groups are
  inferred: each code goes to the race group whose county shares (ACS
  householders) its county shares track best. Census: ACS B11001A-I (race
  and Hispanic origin of the householder).

Census figures are downloaded from the Census API on the first run and kept
in benchmarks/ (public data). The maps use the ACS 2015-2019 5-year
estimates, which still use the 2010 tracts that the infoUSA codes use.

Outputs (aggregates only): output/tables/*.csv, output/figures/*.png,
output/logs/demographics.md. Tract-level infoUSA shares stay in
derived/demographics/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import census, db, geo, paths, settings  # noqa: E402
from flood_ra.report import mask, pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "demographics.md"
TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURES = paths.REPO_ROOT / "output" / "figures"
PRIVATE = paths.DERIVED / "demographics"
GROUPS_FILE = paths.REPO_ROOT / "config" / "ethnicity_groups.yaml"
MAP_YEAR = 2017          # infoUSA year for the maps (middle of ACS 2015-2019)
ACS5_YEAR = 2019         # ACS 2015-2019: the last 5-year release on 2010 tracts
MIN_HH = 30              # areas with fewer infoUSA households are not shown
MIN_CODE_SHARE = 0.002   # ethnicity codes rarer than this are grouped as other
GROUPS = ["white", "black", "hispanic", "asian"]
COLORS = {"NC": "#1f5fa8", "SC": "#c8611c"}

HH = "trim(PRIMARY_FAMILY_IND) = '1'"
INT = "TRY_CAST(trim(\"{}\") AS INTEGER)"


def household_sql(src: str, by: str, universe: str = HH) -> str:
    """Per-group household measures from one converted infoUSA file."""
    own, kids, n_kids = INT.format("OWNER_RENTER_STATUS"), INT.format("CHILDREN_IND"), INT.format("CHILDRENHHCOUNT")
    inc, wealth, home = INT.format("FIND_DIV_1000"), INT.format("WEALTH_FINDER_SCORE"), INT.format("ESTMTD_HOME_VAL_DIV_1000")
    return f"""
        SELECT {by}, count(*) AS households,
               count(*) FILTER (WHERE {own} BETWEEN 7 AND 9) AS owners,
               count(*) FILTER (WHERE {own} BETWEEN 0 AND 3) AS renters,
               count(*) FILTER (WHERE {own} BETWEEN 0 AND 9) AS status_coded,
               count(*) FILTER (WHERE {own} = 9) AS owners_reported,
               count(*) FILTER (WHERE {own} = 0) AS renters_reported,
               count({kids}) AS kids_known,
               count(*) FILTER (WHERE {kids} = 1) AS with_children,
               avg({n_kids}) AS children_per_hh,
               count(*) FILTER (WHERE {n_kids} >= 3) AS three_plus_children,
               median({inc}) * 1000 AS median_income, avg({inc}) * 1000 AS mean_income,
               count(*) FILTER (WHERE {inc} >= 500) AS income_topcoded, count({inc}) AS income_known,
               median({wealth}) * 1000 AS median_wealth, avg({wealth}) * 1000 AS mean_wealth,
               median({home}) FILTER (WHERE {own} BETWEEN 7 AND 9 AND {home} > 0) * 1000 AS median_home_value
        FROM {src} WHERE {universe} AND upper(trim(STATE)) IN ({", ".join(f"'{s}'" for s in geo.study_states())})
        GROUP BY ALL
    """


def eth_sql(src: str, by: str, universe: str = HH) -> str:
    """Households per Ethnicity_Code_1 value (blank and 00 = missing)."""
    return f"""
        SELECT {by}, coalesce(nullif(nullif(upper(trim(Ethnicity_Code_1)), ''), '00'), '(missing)') AS code,
               count(*) AS households
        FROM {src} WHERE {universe} AND upper(trim(STATE)) IN ({", ".join(f"'{s}'" for s in geo.study_states())})
        GROUP BY ALL
    """


def derive(hh: pd.DataFrame, eth: pd.DataFrame, code_group: dict) -> pd.DataFrame:
    """Shares from the counts: race groups, owners, children."""
    eth = eth.assign(group=eth["code"].map(code_group).fillna("other"))
    known = eth[eth["group"] != "missing"].groupby(["state", "year"])["households"].sum()
    for g in GROUPS:
        s = eth[eth["group"] == g].groupby(["state", "year"])["households"].sum()
        hh = hh.merge((s / known).rename(f"{g}_share").reset_index(), on=["state", "year"], how="left")
        hh[f"{g}_share"] = hh[f"{g}_share"].fillna(0)
    miss = eth[eth["group"] == "missing"].groupby(["state", "year"])["households"].sum()
    hh = hh.merge((miss / eth.groupby(["state", "year"])["households"].sum()).rename("ethnicity_missing")
                  .reset_index(), on=["state", "year"], how="left")
    hh["owner_share"] = hh["owners"] / (hh["owners"] + hh["renters"])
    hh["owner_share_duke"] = hh["owners"] / hh["status_coded"]
    hh["owner_share_reported"] = hh["owners_reported"] / (hh["owners_reported"] + hh["renters_reported"])
    hh["status_unknown"] = 1 - (hh["owners"] + hh["renters"]) / hh["households"]
    hh["children_share"] = hh["with_children"] / hh["kids_known"]
    return hh


def infer_groups(eth_county: pd.DataFrame, acs_county: pd.DataFrame | None) -> pd.DataFrame:
    """Race group of each ethnicity code: from config/ethnicity_groups.yaml, or
    the ACS householder group whose county shares best track the code's."""
    totals = eth_county.groupby("code")["households"].sum()
    share = totals / totals.sum()
    rows = pd.DataFrame({"code": totals.index, "households": totals.values, "share": share.values})
    if GROUPS_FILE.exists():
        # BaseLoader keeps every key a string (safe_load reads the code NO as false)
        given = {str(k).upper(): str(v).lower()
                 for k, v in (yaml.load(GROUPS_FILE.read_text(), Loader=yaml.BaseLoader) or {}).items()}
        rows["group"] = rows["code"].map(given).fillna("other")
        rows.loc[rows["code"] == "(missing)", "group"] = "missing"
        rows["source"] = f"{GROUPS_FILE.name}"
        return rows
    rows["group"], rows["source"] = "other", "too rare to infer"
    for g in GROUPS:
        rows[f"r_{g}"] = np.nan
    if acs_county is None:
        rows["source"] = "no Census county data: not inferred"
    else:
        c = acs_county.set_index("geoid")
        bench = pd.DataFrame({
            "white": c["householders_white_nh"], "black": c["householders_black"],
            "hispanic": c["householders_hispanic"], "asian": c["householders_asian"],
        }).div(c["householders"], axis=0)
        known = eth_county[eth_county["code"] != "(missing)"]
        wide = known.pivot_table(index="county", columns="code", values="households", aggfunc="sum", fill_value=0)
        wide = wide.div(wide.sum(axis=1), axis=0)
        wide = wide.loc[wide.index.intersection(bench.index)]
        b = bench.loc[wide.index]
        for i, r in rows.iterrows():
            if r["code"] == "(missing)":
                rows.loc[i, ["group", "source"]] = ["missing", "missing code"]
                continue
            if r["share"] < MIN_CODE_SHARE or r["code"] not in wide:
                continue
            corr = {g: np.corrcoef(wide[r["code"]], b[g])[0, 1] for g in GROUPS}
            for g, v in corr.items():
                rows.loc[i, f"r_{g}"] = v
            ranked = sorted((v for v in corr.values() if not np.isnan(v)), reverse=True) + [-1, -1]
            best = max(corr, key=lambda g: -np.inf if np.isnan(corr[g]) else corr[g])
            # a clear match: r >= 0.4 and at least 0.15 above the next group
            if ranked[0] >= 0.4 and ranked[0] - ranked[1] >= 0.15:
                rows.loc[i, ["group", "source"]] = [best, "inferred from county shares"]
            else:
                rows.loc[i, "source"] = "no clear match"
    rows.loc[rows["code"] == "(missing)", ["group", "source"]] = ["missing", "missing code"]
    return rows


def plot_trends(state: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    panels = [
        ("Owner share (unknown codes count as renters)", "owner_share_duke", "census_owner_share", "{:.0%}"),
        ("Households with children", "children_share", "census_children_share", "{:.0%}"),
        ("Children per household", "children_per_hh", "census_children_per_hh", "{:.2f}"),
        ("Median household income ($)", "median_income", "census_median_income", "{:,.0f}"),
        ("Median wealth ($, infoUSA model)", "median_wealth", None, "{:,.0f}"),
        ("Median home value, owners ($)", "median_home_value", "census_median_home_value", "{:,.0f}"),
        ("Black share of households", "black_share", "census_black_share", "{:.0%}"),
        ("Hispanic share of households", "hispanic_share", "census_hispanic_share", "{:.0%}"),
        ("White (non-Hispanic) share", "white_share", "census_white_share", "{:.0%}"),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, (title, ours, cen, fmt) in zip(axes.flat, panels):
        for st, d in state.groupby("state"):
            d = d.sort_values("year")
            ax.plot(d["year"], d[ours], "-", color=COLORS.get(st), lw=2, label=f"{st} infoUSA, primary families")
            if f"{ours}_all" in d:
                ax.plot(d["year"], d[f"{ours}_all"], ":", color=COLORS.get(st), lw=1.6,
                        label=f"{st} infoUSA, all family records")
            if cen and cen in d and d[cen].notna().any():
                ax.plot(d["year"], d[cen], "--o", color=COLORS.get(st), ms=3, lw=1.2, label=f"{st} Census (ACS)")
        ax.set_title(title, fontsize=11)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _, f=fmt: f.format(v)))
        ax.axvline(2018.7, color="grey", lw=0.8, ls=":")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.grid(alpha=0.3)
    axes.flat[0].legend(fontsize=8, loc="best")
    fig.suptitle("infoUSA households (primary families) vs Census ACS, NC and SC. "
                 "Dotted line: Hurricane Florence (Sept 2018)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_maps(shapes, tracts: pd.DataFrame, acs_tracts: pd.DataFrame | None, states_outline,
              col: str, census_col: str, title: str, cmap: str, vmin: float, vmax: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    have_census = acs_tracts is not None and census_col in acs_tracts
    fig, axes = plt.subplots(1, 2 if have_census else 1, figsize=(16 if have_census else 9, 6.5))
    axes = np.atleast_1d(axes)
    sources = [("infoUSA " + str(MAP_YEAR), tracts, col)]
    if have_census:
        sources.append((f"Census ACS {ACS5_YEAR - 4}-{ACS5_YEAR}", acs_tracts, census_col))
    for ax, (label, data, c) in zip(axes, sources):
        g = shapes.merge(data[["geoid", c]], on="geoid", how="left")
        g.plot(ax=ax, color="#d9d9d9", linewidth=0)
        g[g[c].notna()].plot(ax=ax, column=c, cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0)
        states_outline.boundary.plot(ax=ax, color="black", linewidth=0.6)
        ax.set_title(label)
        ax.set_axis_off()
    sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(vmin, vmax))
    fig.colorbar(sm, ax=list(axes), shrink=0.7, label=title)
    fig.suptitle(f"{title}, by 2010 census tract (grey: fewer than {MIN_HH} infoUSA households or no data)")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    files = paths.chosen_files()
    if not files:
        sys.exit(f"no converted files in {paths.INFOUSA_PARQUET}; run step 01 first")
    for d in (TABLES, FIGURES, PRIVATE):
        d.mkdir(parents=True, exist_ok=True)
    states = geo.study_states()
    fips = [geo.STATE_FIPS[s] for s in states]
    postal = {v: k for k, v in geo.STATE_FIPS.items()}
    fam = settings.GEO_FAMILY
    con = db.connect(threads=paths.THREADS * paths.PARALLEL)
    geo.define_macros(con)
    notes = []

    # 1. infoUSA measures by state-year, and ethnicity codes by state-year
    # (and the same over all family records, subfamilies included: suffix _all)
    hh, eth, hh_all, eth_all = [], [], [], []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        hh.append(con.sql(household_sql(src, "upper(trim(STATE)) AS state")).df().assign(year=year))
        eth.append(con.sql(eth_sql(src, "upper(trim(STATE)) AS state")).df().assign(year=year))
        hh_all.append(con.sql(household_sql(src, "upper(trim(STATE)) AS state", "true")).df().assign(year=year))
        eth_all.append(con.sql(eth_sql(src, "upper(trim(STATE)) AS state", "true")).df().assign(year=year))
        print(f"{year}: households measured", flush=True)
    hh, eth = pd.concat(hh, ignore_index=True), pd.concat(eth, ignore_index=True)
    hh_all, eth_all = pd.concat(hh_all, ignore_index=True), pd.concat(eth_all, ignore_index=True)

    # 2. small areas in the map year: counties (to infer ethnicity groups) and tracts (maps)
    map_file = files.get(MAP_YEAR)
    acs_county, n1 = census.small_areas(ACS5_YEAR, "county", fips)
    acs_tract, n2 = census.small_areas(ACS5_YEAR, "tract", fips)
    notes += n1 + n2
    eth_county = tracts = None
    if map_file is not None:
        src = f"read_parquet('{map_file.as_posix()}')"
        eth_county = con.sql(eth_sql(src, f"{geo.county_fips(fam)} AS county")).df().dropna(subset=["county"])
        tracts = con.sql(household_sql(src, f"{geo.tract_geoid(fam)} AS geoid")).df().dropna(subset=["geoid"])
        tract_eth = con.sql(eth_sql(src, f"{geo.tract_geoid(fam)} AS geoid")).df().dropna(subset=["geoid"])
    else:
        notes.append(f"no infoUSA file for {MAP_YEAR}: no maps, ethnicity groups not inferred")

    # 3. ethnicity code -> group
    # with a groups file, map every code seen in any year (codes such as Q6-Q8 start in 2018)
    groups = infer_groups(eth.rename(columns={"state": "county"}) if GROUPS_FILE.exists() or eth_county is None
                          else eth_county,
                          acs_county)
    code_group = dict(zip(groups["code"], groups["group"]))
    eth["group"] = eth["code"].map(code_group).fillna("other")
    hh = derive(hh, eth, code_group)
    hh_all = derive(hh_all, eth_all, code_group)
    hh = hh.merge(hh_all.drop(columns=["ethnicity_missing"]), on=["state", "year"], suffixes=("", "_all"))

    # 4. Census state series
    acs, n3 = census.state_series(sorted(hh["year"].unique()), fips)
    notes += n3
    if len(acs):
        a = acs.copy()
        a["state"] = a["state"].astype(str).str.zfill(2).map(postal)
        a["census_households"] = a["households"]
        a["census_owner_share"] = a["owner_households"] / a["households"]
        a["census_children_share"] = a["households_with_children"] / a["households_b11005"]
        a["census_children_per_hh"] = a["children_in_households"] / a["households"]
        a["census_median_income"] = a["median_household_income"]
        a["census_median_home_value"] = a["median_home_value"]
        a["census_white_share"] = a["householders_white_nh"] / a["householders"]
        a["census_black_share"] = a["householders_black"] / a["householders"]
        a["census_hispanic_share"] = a["householders_hispanic"] / a["householders"]
        a["census_asian_share"] = a["householders_asian"] / a["householders"]
        hh = hh.merge(a[["state", "year"] + [c for c in a if c.startswith("census_")]],
                      on=["state", "year"], how="left")
    else:
        notes.append("no Census state data: trends show infoUSA only")

    hh = hh.sort_values(["state", "year"])
    hh.to_csv(TABLES / "demographics_state_year.csv", index=False)
    eth_out = eth.assign(code=eth["code"].map(lambda v: v if v == "(missing)" else mask(v)))
    eth_out.to_csv(TABLES / "ethnicity_codes_state_year.csv", index=False)
    groups.assign(code=groups["code"].map(lambda v: v if v == "(missing)" else mask(v))).to_csv(
        TABLES / "ethnicity_code_groups.csv", index=False)
    plot_trends(hh, FIGURES / "demographic_trends.png")

    # 5. maps and tract-level comparison
    map_lines = []
    if tracts is not None:
        tracts = tracts[tracts["households"] >= MIN_HH].copy()
        tracts["owner_share"] = tracts["owners"] / (tracts["owners"] + tracts["renters"])
        tracts["owner_share_duke"] = tracts["owners"] / tracts["status_coded"]
        tract_eth["group"] = tract_eth["code"].map(code_group).fillna("other")
        te = tract_eth.pivot_table(index="geoid", columns="group", values="households", aggfunc="sum", fill_value=0)
        for g in ("white", "black"):
            if g not in te:
                te[g] = 0
        wb = te["white"] + te["black"]
        tracts = tracts.merge((te["black"] / wb.where(wb > 0)).rename("black_share_wb").reset_index(),
                              on="geoid", how="left")
        tracts.to_csv(PRIVATE / f"tracts_{MAP_YEAR}.csv", index=False)
        at = None
        if acs_tract is not None:
            at = acs_tract.copy()
            at["census_owner_share"] = at["owner_households"] / at["households"]
            wbc = at["householders_white_nh"] + at["householders_black"]
            at["census_black_share_wb"] = at["householders_black"] / wbc.where(wbc > 0)
            both = tracts.merge(at, on="geoid")
            for ours, cen, label in (("owner_share_duke", "census_owner_share", "owner share, unknowns as renters"),
                                     ("owner_share", "census_owner_share", "owner share, known codes only"),
                                     ("black_share_wb", "census_black_share_wb", "Black share of Black+White")):
                ok = both[[ours, cen]].dropna()
                r = np.corrcoef(ok[ours], ok[cen])[0, 1] if len(ok) > 2 else np.nan
                map_lines.append([label, f"{len(ok):,}", f"{r:.2f}", pct(ok[ours].mean()), pct(ok[cen].mean())])
        try:
            shapes = census.boundaries("tract", fips)
            counties = census.boundaries("county", fips)
            outline = counties.assign(st=counties["geoid"].str[:2]).dissolve("st")
            plot_maps(shapes, tracts, at, outline, "black_share_wb", "census_black_share_wb",
                      "Black share of Black and White households", "PuOr", 0, 1,
                      FIGURES / f"map_race_{MAP_YEAR}.png")
            plot_maps(shapes, tracts, at, outline, "owner_share_duke", "census_owner_share",
                      "Owner share of households (unknown codes count as renters)", "YlGnBu", 0.2, 1,
                      FIGURES / f"map_owners_{MAP_YEAR}.png")
        except Exception as e:  # noqa: BLE001
            notes.append(f"maps not drawn: {type(e).__name__}: {str(e).splitlines()[0][:150] if str(e) else ''}")

    # 6. report
    def fmt(df: pd.DataFrame, cols: dict) -> pd.DataFrame:
        out = df[["year", "state"] + [c for c in cols if c in df]].copy()
        for c, kind in cols.items():
            if c in out:
                out[c] = out[c].map(lambda v, k=kind: "" if pd.isna(v) else (pct(v) if k == "%" else f"{v:,.{k}f}"))
        return out.rename(columns={c: c.replace("census_", "ACS ").replace("_", " ") for c in cols})

    show = groups.copy()
    show["code"] = show["code"].map(lambda v: v if v == "(missing)" else mask(v))
    show = show.sort_values("households", ascending=False).head(40)
    show["share"] = show["share"].map(pct)
    for g in GROUPS:
        if f"r_{g}" in show:
            show[f"r_{g}"] = show[f"r_{g}"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    REPORT.write_text("\n".join([
        "# Demographics: infoUSA vs Census (aggregates only)", "",
        "Households = primary families (PRIMARY_FAMILY_IND = 1), study states. Census = ACS 1-year "
        "state estimates (no 2020 release). Figures: `output/figures/`; full tables: "
        f"`output/tables/`. {census.cache_note()}", "",
        *([("Notes: " + "; ".join(notes)), ""] if notes else []),
        "## Primary families vs all family records", "",
        "Does counting subfamilies too (all family records) bring infoUSA closer to the Census? "
        "Each measure three ways: primary families (prim.), all family records (all) and ACS.", "",
        *table(fmt(hh, {"households": "0", "households_all": "0", "census_households": "0",
                        "owner_share_duke": "%", "owner_share_duke_all": "%", "census_owner_share": "%",
                        "children_share": "%", "children_share_all": "%", "census_children_share": "%"})
               .rename(columns=lambda c: c.replace(" all", " (all)"))),
        *table(fmt(hh, {"median_income": "0", "median_income_all": "0", "census_median_income": "0",
                        "black_share": "%", "black_share_all": "%", "census_black_share": "%",
                        "hispanic_share": "%", "hispanic_share_all": "%", "census_hispanic_share": "%"})
               .rename(columns=lambda c: c.replace(" all", " (all)"))),
        "## Owners and renters (primary families)", "",
        "owner share duke (plotted): OWNER_RENTER_STATUS 7-9 among households coded 0-9, so the "
        "unknowns (4-6) count as renters, as in the Duke DPRC report's Table 6; it moves with Data "
        "Axle's recoding of unknowns (2015, 2019, 2025). owner share: 7-9 among households with 0-3 or "
        "7-9; reported: 9 among 9 and 0; status unknown: share coded 4-6 or missing.", "",
        *table(fmt(hh, {"households": "0", "owner_share_duke": "%", "owner_share": "%", "owner_share_reported": "%",
                        "status_unknown": "%", "census_owner_share": "%", "census_households": "0"})),
        "## Children", "",
        *table(fmt(hh, {"children_share": "%", "census_children_share": "%", "children_per_hh": "2",
                        "census_children_per_hh": "2"})),
        "## Income, wealth and home value (nominal dollars)", "",
        "infoUSA income is top-coded at $500,000 (share top-coded shown); wealth has no Census "
        "benchmark.", "",
        *table(fmt(hh.assign(topcoded=hh["income_topcoded"] / hh["income_known"]),
                   {"median_income": "0", "census_median_income": "0", "topcoded": "%",
                    "median_wealth": "0", "mean_wealth": "0", "median_home_value": "0",
                    "census_median_home_value": "0"})),
        "## Race and ethnicity of the first person / householder", "",
        "Shares of households with a known ethnicity code; ethnicity missing: share with code 00 "
        "or blank. Census: race and Hispanic origin of the householder (white = non-Hispanic).", "",
        *table(fmt(hh, {"ethnicity_missing": "%", "white_share": "%", "census_white_share": "%",
                        "black_share": "%", "census_black_share": "%", "hispanic_share": "%",
                        "census_hispanic_share": "%", "asian_share": "%", "census_asian_share": "%"})),
        "### Ethnicity codes and their groups", "",
        f"Most common Ethnicity_Code_1 values (all years; codes longer than 4 characters shown as "
        f"patterns). group: from `config/{GROUPS_FILE.name}` if it exists, else inferred: r_* is "
        f"the correlation, across counties in {MAP_YEAR}, of the code's share of households with the "
        "ACS share of each householder group; a code goes to the best group if r >= 0.4 and at least "
        "0.15 above the next group. "
        "**Check the inferred groups against the Data Axle Ethnicity-Cultural Coding Datacard.**", "",
        *table(show.drop(columns=["households"])),
        f"## Tracts, {MAP_YEAR} (infoUSA) vs ACS {ACS5_YEAR - 4}-{ACS5_YEAR}", "",
        f"Tracts with at least {MIN_HH} infoUSA households. r: correlation across tracts; means are "
        "unweighted tract means.", "",
        *(table(pd.DataFrame(map_lines, columns=["measure", "tracts", "r", "infoUSA mean", "ACS mean"]))
          if map_lines else ["(no Census tract data)", ""]),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
