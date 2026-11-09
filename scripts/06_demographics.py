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
- wealth: WEALTH_FINDER_SCORE ($ thousands). No Census benchmark exists, so it
  is only in the CSV table, not in the figure or the report.
- home value: ESTMTD_HOME_VAL_DIV_1000 of likely owners. Census: ACS B25077.
- race / ethnicity: Ethnicity_Code_1 of the first person, grouped with the
  code table config/ethnicity_codes.csv and the categories in
  src/flood_ra/ethnicity.py (LR counts as Black American). Shares are of
  households with a placed code: unknown codes (00, ZZ, blank) and codes no
  rule places are left out. Census: ACS B11001A-I (race and Hispanic origin
  of the householder).

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import census, db, ethnicity, geo, paths, settings  # noqa: E402
from flood_ra.report import mask, pct, table  # noqa: E402

REPORT = paths.LOG_DIR / "demographics.md"
TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURES = paths.REPO_ROOT / "output" / "figures"
PRIVATE = paths.DERIVED / "demographics"
MAP_YEAR = 2017          # infoUSA year for the maps (middle of ACS 2015-2019)
ACS5_YEAR = 2019         # ACS 2015-2019: the last 5-year release on 2010 tracts
MIN_HH = 30              # areas with fewer infoUSA households are not shown
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
    """Households per Ethnicity_Code_1 value of the first person."""
    return f"""
        SELECT {by}, coalesce(nullif(upper(trim(Ethnicity_Code_1)), ''), '{ethnicity.BLANK}') AS code,
               count(*) AS households
        FROM {src} WHERE {universe} AND upper(trim(STATE)) IN ({", ".join(f"'{s}'" for s in geo.study_states())})
        GROUP BY ALL
    """


def classify(eth: pd.DataFrame) -> pd.DataFrame:
    """Add each code's Data Axle group, category and broad group (see ethnicity.py)."""
    codes = pd.Series(eth["code"].unique(), dtype=object)
    raw = codes.where(codes != ethnicity.BLANK, "")
    look = pd.DataFrame({"code": codes, "group": raw.map(ethnicity.group), "category": raw.map(ethnicity.category)})
    look["broad"] = look["category"].map(ethnicity.CATEGORIES)
    return eth.drop(columns=[c for c in ("group", "category", "broad") if c in eth]).merge(look, on="code", how="left")


def derive(hh: pd.DataFrame, eth: pd.DataFrame) -> pd.DataFrame:
    """Shares from the counts: race groups, owners, children."""
    by = ["state", "year"]
    total = eth.groupby(by)["households"].sum()
    placed = eth[eth["broad"].notna()]
    n_placed = placed.groupby(by)["households"].sum().reindex(total.index)
    out = pd.DataFrame(index=total.index)
    for g in ethnicity.BROAD_GROUPS:
        n = placed[placed["broad"] == g].groupby(by)["households"].sum().reindex(total.index, fill_value=0)
        out[f"{g}_share"] = n / n_placed
    for col, cat in (("ethnicity_unknown", ethnicity.UNKNOWN), ("ethnicity_not_placed", ethnicity.NOT_PLACED)):
        out[col] = eth[eth["category"] == cat].groupby(by)["households"].sum().reindex(total.index, fill_value=0) / total
    hh = hh.merge(out.reset_index(), on=by, how="left")
    hh["owner_share"] = hh["owners"] / (hh["owners"] + hh["renters"])
    hh["owner_share_duke"] = hh["owners"] / hh["status_coded"]
    hh["owner_share_reported"] = hh["owners_reported"] / (hh["owners_reported"] + hh["renters_reported"])
    hh["status_unknown"] = 1 - (hh["owners"] + hh["renters"]) / hh["households"]
    hh["children_share"] = hh["with_children"] / hh["kids_known"]
    return hh


def category_table(eth: pd.DataFrame) -> pd.DataFrame:
    """Households per category by state and year. Share of placed households for
    the categories; share of all households for Unknown and Not placed."""
    by = ["state", "year"]
    t = eth.groupby(by + ["category"], as_index=False)["households"].sum()
    is_cat = t["category"].isin(list(ethnicity.CATEGORIES))
    t = t.merge(t[is_cat].groupby(by)["households"].sum().rename("placed").reset_index(), on=by, how="left")
    t = t.merge(t.groupby(by)["households"].sum().rename("total").reset_index(), on=by)
    t["share"] = np.where(t["category"].isin(list(ethnicity.CATEGORIES)), t["households"] / t["placed"],
                          t["households"] / t["total"])
    return t.drop(columns=["placed", "total"])


def plot_trends(state: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    panels = [
        ("Owner share (unknown codes count as renters)", "owner_share_duke", "census_owner_share", "{:.0%}"),
        ("Households with children", "children_share", "census_children_share", "{:.0%}"),
        ("Children per household", "children_per_hh", "census_children_per_hh", "{:.2f}"),
        ("Median household income ($)", "median_income", "census_median_income", "{:,.0f}"),
        ("Median home value, owners ($)", "median_home_value", "census_median_home_value", "{:,.0f}"),
        ("Black share of households", "black_share", "census_black_share", "{:.0%}"),
        ("Hispanic share of households", "hispanic_share", "census_hispanic_share", "{:.0%}"),
        ("White (non-Hispanic) share", "white_share", "census_white_share", "{:.0%}"),
    ]
    ncols = 4
    nrows = -(-len(panels) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4.3 * nrows), squeeze=False)
    for ax in axes.flat[len(panels):]:
        ax.set_visible(False)
    for ax, (title, ours, cen, fmt) in zip(axes.flat, panels):
        for st, d in state.groupby("state"):
            d = d.sort_values("year")
            ax.plot(d["year"], d[ours], "-", color=COLORS.get(st), lw=2, label=f"{st} infoUSA")
            if cen and cen in d and d[cen].notna().any():
                ax.plot(d["year"], d[cen], "--o", color=COLORS.get(st), ms=3, lw=1.2, label=f"{st} Census (ACS)")
        ax.set_title(title, fontsize=11)
        # tick steps of 1, 2 or 5 (not 2.5), so whole-number labels are exact
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(steps=[1, 2, 5, 10]))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _, f=fmt: f.format(v)))
        ax.axvline(2018.7, color="grey", lw=0.8, ls=":")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.grid(alpha=0.3)
    axes.flat[0].legend(fontsize=8, loc="best")
    fig.suptitle("infoUSA households (primary families) vs Census ACS, NC and SC. "
                 "Dotted line: Hurricane Florence (Sept 2018)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
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
    hh, eth = [], []
    for year, f in files.items():
        src = f"read_parquet('{f.as_posix()}')"
        hh.append(con.sql(household_sql(src, "upper(trim(STATE)) AS state")).df().assign(year=year))
        eth.append(con.sql(eth_sql(src, "upper(trim(STATE)) AS state")).df().assign(year=year))
        print(f"{year}: households measured", flush=True)
    hh, eth = pd.concat(hh, ignore_index=True), pd.concat(eth, ignore_index=True)

    # 2. tracts in the map year (maps)
    map_file = files.get(MAP_YEAR)
    acs_tract, n2 = census.small_areas(ACS5_YEAR, "tract", fips)
    notes += n2
    tracts = None
    if map_file is not None:
        src = f"read_parquet('{map_file.as_posix()}')"
        tracts = con.sql(household_sql(src, f"{geo.tract_geoid(fam)} AS geoid")).df().dropna(subset=["geoid"])
        tract_eth = classify(con.sql(eth_sql(src, f"{geo.tract_geoid(fam)} AS geoid")).df().dropna(subset=["geoid"]))
    else:
        notes.append(f"no infoUSA file for {MAP_YEAR}: no maps")

    # 3. ethnicity code -> Data Axle group -> category -> broad group (ethnicity.py)
    eth = classify(eth)
    hh = derive(hh, eth)
    cats = category_table(eth)
    codes = eth.groupby(["code", "group", "category"], as_index=False)["households"].sum()
    codes["broad"] = codes["category"].map(ethnicity.CATEGORIES)
    codes["share"] = codes["households"] / codes["households"].sum()
    codes["in_table"] = codes["code"].map(lambda c: c == ethnicity.BLANK or c in ethnicity.load_codes())
    codes = codes.sort_values("households", ascending=False)
    show_code = lambda v: v if v == ethnicity.BLANK else mask(v)  # noqa: E731

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
    eth.assign(code=eth["code"].map(show_code)).to_csv(TABLES / "ethnicity_codes_state_year.csv", index=False)
    codes.assign(code=codes["code"].map(show_code)).to_csv(TABLES / "ethnicity_code_groups.csv", index=False)
    cats.to_csv(TABLES / "ethnicity_categories_state_year.csv", index=False)
    plot_trends(hh, FIGURES / "demographic_trends.png")

    # 5. maps and tract-level comparison
    map_lines = []
    if tracts is not None:
        tracts = tracts[tracts["households"] >= MIN_HH].copy()
        tracts["owner_share"] = tracts["owners"] / (tracts["owners"] + tracts["renters"])
        tracts["owner_share_duke"] = tracts["owners"] / tracts["status_coded"]
        te = tract_eth[tract_eth["broad"].isin(["white", "black"])].pivot_table(
            index="geoid", columns="broad", values="households", aggfunc="sum", fill_value=0)
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

    show = codes.head(40).assign(code=lambda d: d["code"].map(show_code), share=lambda d: d["share"].map(pct))
    absent = codes[~codes["in_table"]]
    absent_line = ("Codes in the data but not in the table (so not placed): " + ", ".join(
        f"{show_code(c)} ({n:,} households)" for c, n in zip(absent["code"][:20], absent["households"][:20]))
        + (f", and {len(absent) - 20} more" if len(absent) > 20 else "") + "."
        if len(absent) else "Every code in the data is in the table.")
    wide = cats.pivot_table(index=["state", "year"], columns="category", values="share", aggfunc="sum")
    order = [c for c in [ethnicity.UNKNOWN, ethnicity.NOT_PLACED, *ethnicity.CATEGORIES] if c in wide]
    wide = wide[order].fillna(0).map(pct).reset_index()
    wide = wide[["year", "state", *order]]
    wide.columns.name = None
    recodes = ", ".join(str(y) for y in (2015, 2019, 2025) if y in set(hh["year"])) or "none in these years"
    REPORT.write_text("\n".join([
        "# Demographics: infoUSA vs Census (aggregates only)", "",
        "Households = primary families (PRIMARY_FAMILY_IND = 1), study states. Census = ACS 1-year "
        "state estimates (no 2020 release). Figures: `output/figures/`; full tables: "
        f"`output/tables/`. {census.cache_note()}", "",
        *([("Notes: " + "; ".join(notes)), ""] if notes else []),
        "## Owners and renters (primary families)", "",
        "owner share duke (plotted): OWNER_RENTER_STATUS 7-9 among households coded 0-9, so the "
        "unknowns (4-6) count as renters, as in the Duke DPRC report's Table 6; it moves with Data "
        f"Axle's recoding of unknowns ({recodes}). owner share: 7-9 among households with 0-3 or "
        "7-9; reported: 9 among 9 and 0; status unknown: share coded 4-6 or missing.", "",
        *table(fmt(hh, {"households": "0", "owner_share_duke": "%", "owner_share": "%", "owner_share_reported": "%",
                        "status_unknown": "%", "census_owner_share": "%", "census_households": "0"})),
        "## Children", "",
        *table(fmt(hh, {"children_share": "%", "census_children_share": "%", "children_per_hh": "2",
                        "census_children_per_hh": "2"})),
        "## Income and home value (nominal dollars)", "",
        "infoUSA income is top-coded at $500,000 (share top-coded shown). Wealth "
        "(WEALTH_FINDER_SCORE) has no Census benchmark and is left out; it stays in "
        "`output/tables/demographics_state_year.csv`.", "",
        *table(fmt(hh.assign(topcoded=hh["income_topcoded"] / hh["income_known"]),
                   {"median_income": "0", "census_median_income": "0", "topcoded": "%",
                    "median_home_value": "0", "census_median_home_value": "0"})),
        "## Race and ethnicity of the first person / householder", "",
        "Ethnicity_Code_1 of the first person, grouped with the code table "
        "`config/ethnicity_codes.csv` (the Data Axle group of each code) and the categories in "
        "`src/flood_ra/ethnicity.py`: white = White (groups W, S; AU, NZ) + Ethnic White (groups J, "
        "M, E; Portuguese, Basque); black = Black American (B5, LR, Q6-Q9) + Other Black (the rest "
        "of group B); hispanic = H5; asian = East Asian (group F) + South Asian (group A). Race "
        "shares are of households with a placed code. ethnicity unknown (00, ZZ or blank) and not "
        "placed (codes no rule places, such as GY and MV) are shares of all households. Census: race "
        "and Hispanic origin of the householder (white = non-Hispanic White alone; Black and Asian "
        "alone, any origin).", "",
        *table(fmt(hh, {"ethnicity_unknown": "%", "ethnicity_not_placed": "%", "white_share": "%",
                        "census_white_share": "%", "black_share": "%", "census_black_share": "%",
                        "hispanic_share": "%", "census_hispanic_share": "%", "asian_share": "%",
                        "census_asian_share": "%"})),
        "### Categories", "",
        "Share of households with a placed code (Unknown and Not placed: share of all households). "
        "LR counts as Black American: it is the main Black code until 2017, and in 2018 Data Axle "
        "replaced it with Q6-Q9, so Black American should run smoothly through 2018. Pacific "
        "includes the Philippines (group P), which the Census counts as Asian; the Census also "
        "counts MENA as White.", "",
        *table(wide),
        "### Ethnicity codes", "",
        "Most common Ethnicity_Code_1 values, all years (codes longer than 4 characters shown as "
        f"patterns). {absent_line}", "",
        *table(show[["code", "group", "category", "share"]]),
        f"## Tracts, {MAP_YEAR} (infoUSA) vs ACS {ACS5_YEAR - 4}-{ACS5_YEAR}", "",
        f"Tracts with at least {MIN_HH} infoUSA households. r: correlation across tracts; means are "
        "unweighted tract means.", "",
        *(table(pd.DataFrame(map_lines, columns=["measure", "tracts", "r", "infoUSA mean", "ACS mean"]))
          if map_lines else ["(no Census tract data)", ""]),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
