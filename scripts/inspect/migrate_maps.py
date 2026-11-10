"""Maps of MIGRATE moves for North and South Carolina, 2011-2019.

Built from the tables migrate_explore.py writes (no new pass over the
MIGRATE files) and Census 2010 cartographic boundaries (census.boundaries,
downloaded once). MIGRATE: Agostini, Young, Fitzpatrick, Garg and Pierson,
"Inferring fine-grained migration patterns across the United States", NBER
Working Paper 34263 (2025), arXiv:2503.20989; data from
migrate.tech.cornell.edu.

1. Tracts (2010), NC and SC, all 2011-2019 years pooled: the share of
   residents who moved to another block group in a year; people moving in
   from another county or state, and out to another county or state, per 100
   residents a year. Block-group totals are summed to tracts.
2. States: people moving between each state and NC or SC, in and out
   combined (yearly average, 2011-2019; lower 48 states and DC shown).

Not a pipeline step. Run on the server after migrate_explore.py:
    python scripts/inspect/migrate_maps.py
Writes output/figures/migrate_map_tracts.png, migrate_map_states.png,
output/tables/migrate_tract_rates.csv and output/logs/migrate_maps.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flood_ra import census, geo, paths  # noqa: E402
from flood_ra.report import table  # noqa: E402

TABLES = paths.REPO_ROOT / "output" / "tables"
FIGURES = paths.REPO_ROOT / "output" / "figures"
REPORT = paths.LOG_DIR / "migrate_maps.md"
STUDY = {"37": "NC", "45": "SC"}
MIN_POP = 100        # tracts with fewer residents on average are shown in grey
NOT_SHOWN = {"02", "15", "72"}  # Alaska, Hawaii, Puerto Rico: off the lower-48 map
ALBERS = "EPSG:5070"  # equal-area projection for US maps


def tract_rates() -> pd.DataFrame:
    bg = pd.read_csv(TABLES / "migrate_bg.csv", dtype={"bg": str})
    bg["tract"] = bg["bg"].str[:11]
    cols = ["population", "moved_out", "out_other_county", "out_other_state", "in_other_county", "in_other_state"]
    t = bg.groupby("tract")[cols].sum()
    t["years"] = bg.groupby("tract")["year"].nunique()
    t["avg_population"] = t["population"] / t["years"]
    ok = t["avg_population"] >= MIN_POP
    t["moved_share"] = (t["moved_out"] / t["population"]).where(ok)
    t["in_per_100"] = (100 * (t["in_other_county"] + t["in_other_state"]) / t["population"]).where(ok)
    t["out_per_100"] = (100 * (t["out_other_county"] + t["out_other_state"]) / t["population"]).where(ok)
    t["state"] = t.index.str[:2].map(STUDY)
    return t.reset_index()


def state_flows() -> tuple[pd.DataFrame, int]:
    p = pd.read_csv(TABLES / "migrate_state_pairs.csv").dropna(subset=["origin", "destination"])
    n_years = p["year"].nunique()
    rows = []
    for st in STUDY.values():
        into = p[p["destination"] == st].groupby("origin")["flow"].sum() / n_years
        out_ = p[p["origin"] == st].groupby("destination")["flow"].sum() / n_years
        rows.append(pd.DataFrame({"study_state": st, "other_state": into.index, "direction": "into", "people": into.values}))
        rows.append(pd.DataFrame({"study_state": st, "other_state": out_.index, "direction": "out of", "people": out_.values}))
    return pd.concat(rows, ignore_index=True), n_years


def plot_tracts(rates: pd.DataFrame, path: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fips = list(STUDY)
    shapes = census.boundaries("tract", fips).to_crs(ALBERS)
    counties = census.boundaries("county", fips).to_crs(ALBERS)
    states = counties.assign(st=counties["geoid"].str[:2]).dissolve("st")
    g = shapes.merge(rates, left_on="geoid", right_on="tract", how="left")
    notes = [f"tracts in the boundary files: {len(shapes):,}; with MIGRATE rates: "
             f"{g['moved_share'].notna().sum():,}; grey: no MIGRATE block groups or fewer than "
             f"{MIN_POP} residents on average"]
    hi = np.nanpercentile(pd.concat([rates["in_per_100"], rates["out_per_100"]]).dropna(), 98)
    panels = [("moved_share", "Moved to another block group (share a year)", "YlGnBu", 0,
               np.nanpercentile(rates["moved_share"].dropna(), 98), True),
              ("in_per_100", "Moved in from another county or state (per 100 a year)", "YlOrRd", 0, hi, False),
              ("out_per_100", "Moved out to another county or state (per 100 a year)", "YlOrRd", 0, hi, False)]
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.2))
    for ax, (col, title, cmap, vmin, vmax, share) in zip(axes, panels):
        g.plot(ax=ax, color="#d9d9d9", linewidth=0)
        g[g[col].notna()].plot(ax=ax, column=col, cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0)
        counties.boundary.plot(ax=ax, color="white", linewidth=0.15)
        states.boundary.plot(ax=ax, color="black", linewidth=0.6)
        sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(vmin, vmax))
        cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.05, pad=0.02, extend="max")
        cb.ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(steps=[1, 2, 5, 10]))  # exact labels
        if share:
            cb.ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.set_title(title, fontsize=11)
        ax.set_axis_off()
    notes.append(f"colour scales end at the 98th percentile of tracts (darkest colour = that value or more): "
                 f"moved {panels[0][4]:.0%}, in/out {hi:.1f} per 100")
    fig.suptitle("MIGRATE, NC and SC tracts, 2011-2019 pooled (grey: fewer than "
                 f"{MIN_POP} residents or no data)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return notes


def plot_states(flows: pd.DataFrame, n_years: int, path: Path) -> None:
    """One map: people moving between each state and NC or SC, in and out combined."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fips = [f for f in geo.STATE_FIPS.values() if f not in NOT_SHOWN]
    counties = census.boundaries("county", fips)
    states = counties.assign(st=counties["geoid"].str[:2]).dissolve("st").reset_index().to_crs(ALBERS)
    states["postal"] = states["st"].map({v: k for k, v in geo.STATE_FIPS.items()})
    study = list(STUDY.values())
    total = flows[~flows["other_state"].isin(study)].groupby("other_state")["people"].sum()
    # NC rows hold both directions between NC and SC
    between = flows[(flows["study_state"] == study[0]) & (flows["other_state"] == study[1])]["people"].sum()
    g = states.merge(total.rename("people"), left_on="postal", right_index=True, how="left")
    norm = matplotlib.colors.LogNorm(vmin=max(total.min(), 1), vmax=total.max())
    blues = matplotlib.colors.ListedColormap(plt.cm.Blues(np.linspace(0.18, 1, 256)))  # light blue to dark blue
    fig, ax = plt.subplots(figsize=(12, 7.6))
    g.plot(ax=ax, color="#eeeeee", edgecolor="white", linewidth=0.5)
    g[g["people"].notna()].plot(ax=ax, column="people", cmap=blues, norm=norm, edgecolor="white", linewidth=0.5)
    states[states["postal"].isin(study)].plot(ax=ax, color="#808080", edgecolor="black", linewidth=0.8)
    ax.set_axis_off()
    sm = matplotlib.cm.ScalarMappable(cmap=blues, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.02)
    cb.set_ticks([v for v in (100, 300, 1000, 3000, 10000, 30000, 100000) if norm.vmin <= v <= norm.vmax])
    cb.ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    cb.ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    cb.set_label(f"people a year moving to or from NC or SC (average of {n_years} years, log scale)")
    ax.set_title("MIGRATE: moves between each state and NC or SC, in and out combined, 2011-2019\n"
                 f"NC and SC in grey; between the two: {between:,.0f} people a year. "
                 "Alaska and Hawaii not shown.", fontsize=11)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for f in ("migrate_bg.csv", "migrate_state_pairs.csv"):
        if not (TABLES / f).exists():
            sys.exit(f"{TABLES / f} not found; run scripts/inspect/migrate_explore.py first")
    FIGURES.mkdir(parents=True, exist_ok=True)
    rates = tract_rates()
    rates.round(4).to_csv(TABLES / "migrate_tract_rates.csv", index=False)
    notes = plot_tracts(rates, FIGURES / "migrate_map_tracts.png")
    flows, n_years = state_flows()
    plot_states(flows, n_years, FIGURES / "migrate_map_states.png")

    by_state = rates.dropna(subset=["moved_share"]).groupby("state").agg(
        tracts=("tract", "size"),
        moved_median=("moved_share", "median"), in_median=("in_per_100", "median"),
        out_median=("out_per_100", "median"))
    by_state = pd.DataFrame({
        "tracts": by_state["tracts"].map("{:,}".format),
        "moved (median tract)": by_state["moved_median"].map("{:.1%}".format),
        "in per 100 (median tract)": by_state["in_median"].map("{:.1f}".format),
        "out per 100 (median tract)": by_state["out_median"].map("{:.1f}".format)}).reset_index()
    top = []
    for st in STUDY.values():
        for direction in ("into", "out of"):
            f = flows[(flows["study_state"] == st) & (flows["direction"] == direction)].nlargest(5, "people")
            top.append({"": f"{direction} {st}", **{f"{k + 1}": f"{r.other_state} {r.people:,.0f}"
                                                    for k, r in enumerate(f.itertuples())}})
    REPORT.write_text("\n".join([
        "# MIGRATE maps, NC and SC 2011-2019 (aggregates)", "",
        "Source: MIGRATE (Agostini, Young, Fitzpatrick, Garg and Pierson, NBER Working Paper 34263, 2025; "
        "migrate.tech.cornell.edu). Figures: `output/figures/migrate_map_tracts.png` (tracts) and "
        "`migrate_map_states.png` (states); tract rates: `output/tables/migrate_tract_rates.csv`.", "",
        "Notes: " + "; ".join(notes), "",
        "## Tracts", "",
        "All 2011-2019 years pooled. moved: share of residents who moved to another block group in a "
        "year; in / out: people moving in from (out to) another county or state per 100 residents a "
        "year.", "",
        *table(by_state),
        f"## Top 5 partner states (people a year, average of {n_years} years)", "",
        *table(pd.DataFrame(top)),
    ]))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
