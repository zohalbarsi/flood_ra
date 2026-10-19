"""Census benchmarks (public data) from the Census Bureau API, and 2010 census
boundary files for maps.

Downloaded tables are cached in benchmarks/ (tracked in git, so later runs
and other machines need no download); boundary files are cached in
derived/geo/shapes/. A Census API key is optional: set CENSUS_API_KEY to
avoid the daily limit for keyless use.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from flood_ra import paths

BENCH = paths.REPO_ROOT / "benchmarks"
SHAPES = paths.GEO / "shapes"
API = "https://api.census.gov/data"

# ACS tables. Households = occupied housing units; race and Hispanic origin
# are of the householder (B11001A-I), to compare with infoUSA's first person.
ACS_VARS = {
    "B25003_001E": "households",
    "B25003_002E": "owner_households",
    "B25003_003E": "renter_households",
    "B11005_001E": "households_b11005",
    "B11005_002E": "households_with_children",
    "B09001_001E": "children_in_households",
    "B19013_001E": "median_household_income",
    "B19025_001E": "aggregate_household_income",
    "B25077_001E": "median_home_value",
    "B11001_001E": "householders",
    "B11001A_001E": "householders_white",
    "B11001B_001E": "householders_black",
    "B11001D_001E": "householders_asian",
    "B11001H_001E": "householders_white_nh",
    "B11001I_001E": "householders_hispanic",
}
# Age of householder (B25007: tenure by age of householder), owners + renters
AGE_BANDS = ["15-24", "25-34", "35-44", "45-54", "55-59", "60-64", "65-74", "75-84", "85+"]
AGE_VARS = {"B25007_001E": "households"}
AGE_VARS.update({f"B25007_{3 + i:03d}E": f"owner_{b}" for i, b in enumerate(AGE_BANDS)})
AGE_VARS.update({f"B25007_{13 + i:03d}E": f"renter_{b}" for i, b in enumerate(AGE_BANDS)})

SMALL_AREA_VARS = ["B25003_001E", "B25003_002E", "B25003_003E", "B11001_001E", "B11001A_001E",
                   "B11001B_001E", "B11001D_001E", "B11001H_001E", "B11001I_001E"]


def _get(year: int, dataset: str, variables: list[str], geo_for: str, geo_in: list[str]) -> pd.DataFrame:
    q = [("get", ",".join(["NAME"] + variables)), ("for", geo_for)] + [("in", g) for g in geo_in]
    if os.environ.get("CENSUS_API_KEY"):
        q.append(("key", os.environ["CENSUS_API_KEY"]))
    url = f"{API}/{year}/{dataset}?" + urllib.parse.urlencode(q, safe=":*,")
    req = urllib.request.Request(url, headers={"User-Agent": "flood_ra research pipeline"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            status = r.status
            # redirected to the missing_key / invalid_key page (look at the path only:
            # the query string of a good request holds key=...)
            if "key" in urllib.parse.urlparse(r.geturl()).path.split("/")[-1]:
                LAST_ERROR[0] = ("the Census API needs a key: get one free at "
                                 "https://api.census.gov/data/key_signup.html and set CENSUS_API_KEY")
                DOWN[0] = True
                raise ValueError(LAST_ERROR[0])
    except urllib.error.HTTPError as e:
        LAST_ERROR[0] = f"HTTP {e.code}: {e.read()[:150].decode(errors='replace').strip()}"
        raise
    except (urllib.error.URLError, OSError) as e:
        LAST_ERROR[0] = f"{type(e).__name__}: {e}"[:200]
        DOWN[0] = True  # no connection at all: skip further calls this run
        raise
    try:
        rows = json.loads(body)
    except ValueError:
        LAST_ERROR[0] = f"HTTP {status}, not data: {body[:150].decode(errors='replace').strip() or '(empty reply)'}"
        raise
    return pd.DataFrame(rows[1:], columns=rows[0])


LAST_ERROR = [""]  # why the latest call failed, for the report
DOWN = [False]


def fetch(year: int, dataset: str, variables: list[str], geo_for: str,
          geo_in: list[str] = ()) -> tuple[pd.DataFrame | None, list[str]]:
    """One call for all variables; if that fails, one call per variable, so a
    table missing in some year only loses that variable. Returns the data
    (None if nothing came back) and the variables that could not be fetched."""
    if DOWN[0]:
        return None, list(variables)
    try:
        return _get(year, dataset, variables, geo_for, list(geo_in)), []
    except (urllib.error.URLError, OSError, ValueError):
        if DOWN[0] or "(empty reply)" in LAST_ERROR[0]:
            return None, list(variables)
    out, missing = None, []
    keys = [k for k in ("state", "county", "tract") if f"{k}:" in geo_for or any(f"{k}:" in g for g in geo_in)]
    for v in variables:
        try:
            d = _get(year, dataset, [v], geo_for, list(geo_in)).drop(columns="NAME")
        except (urllib.error.URLError, OSError, ValueError):
            missing.append(v)
            continue
        out = d if out is None else out.merge(d, on=keys, how="outer")
    return out, missing


def _numeric(d: pd.DataFrame, variables: list[str], names: dict = ACS_VARS) -> pd.DataFrame:
    for v in variables:
        if v in d:
            d[v] = pd.to_numeric(d[v], errors="coerce")
            d.loc[d[v] < 0, v] = None  # the API codes "not available" as large negatives
    return d.rename(columns=names)


def state_series(years: list[int], fips: list[str], variables: dict = ACS_VARS,
                 cache_name: str = "acs1_state.csv") -> tuple[pd.DataFrame, list[str]]:
    """ACS 1-year state estimates of `variables` ({API name: column name}),
    one row per state and year (the 2020 1-year release does not exist).
    Cached in benchmarks/<cache_name>."""
    cache = BENCH / cache_name
    have = pd.read_csv(cache, dtype={"state": str}) if cache.exists() else pd.DataFrame()
    notes, new = [], []
    for y in years:
        if y == 2020 or (len(have) and ((have["year"] == y) & have["state"].isin(fips)).sum() == len(fips)):
            continue
        d, missing = fetch(y, "acs/acs1", list(variables), "state:" + ",".join(fips))
        if d is None:
            notes.append(f"ACS 1-year {y}: not available ({LAST_ERROR[0]})")
            continue
        if missing:
            notes.append(f"ACS 1-year {y}: missing {', '.join(missing)}")
        d = _numeric(d.drop(columns="NAME", errors="ignore"), list(variables), variables)
        d.insert(0, "year", y)
        new.append(d)
    if new:
        have = pd.concat([have] + new, ignore_index=True).drop_duplicates(["year", "state"], keep="last")
        BENCH.mkdir(exist_ok=True)
        have.sort_values(["state", "year"]).to_csv(cache, index=False)
    return have[have["state"].isin(fips)] if len(have) else have, notes


def small_areas(year: int, level: str, fips: list[str]) -> tuple[pd.DataFrame | None, list[str]]:
    """ACS 5-year estimates for every county or tract of the states, with a
    `geoid` column. Cached in benchmarks/acs5_<year>_<level>.csv."""
    cache = BENCH / f"acs5_{year}_{level}.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"geoid": str}), []
    parts, notes = [], []
    for st in fips:
        geo_in = [f"state:{st}"] + (["county:*"] if level == "tract" else [])
        d, missing = fetch(year, "acs/acs5", SMALL_AREA_VARS, f"{level}:*", geo_in)
        if d is None:
            notes.append(f"ACS 5-year {year} {"counties" if level == "county" else "tracts"}, state {st}: not available ({LAST_ERROR[0]})")
            continue
        if missing:
            notes.append(f"ACS 5-year {year} {"counties" if level == "county" else "tracts"}, state {st}: missing {', '.join(missing)}")
        d["geoid"] = d["state"] + d["county"] + (d["tract"] if level == "tract" else "")
        parts.append(_numeric(d[["geoid"] + [v for v in SMALL_AREA_VARS if v in d]], SMALL_AREA_VARS))
    if not parts:
        return None, notes
    out = pd.concat(parts, ignore_index=True)
    BENCH.mkdir(exist_ok=True)
    out.to_csv(cache, index=False)
    return out, notes


def boundaries(level: str, fips: list[str]):
    """2010 cartographic boundaries (1:500k) of counties or tracts, with an
    11-digit (tract) or 5-digit (county) `geoid`; downloaded once."""
    import geopandas as gpd
    SHAPES.mkdir(parents=True, exist_ok=True)
    names = ([f"gz_2010_{st}_140_00_500k.zip" for st in fips] if level == "tract"
             else ["gz_2010_us_050_00_500k.zip"])
    frames = []
    for name in names:
        f = SHAPES / name
        if not f.exists():
            tmp = f.with_suffix(".part")
            urllib.request.urlretrieve(f"https://www2.census.gov/geo/tiger/GENZ2010/{name}", tmp)
            tmp.replace(f)
        frames.append(gpd.read_file(f"zip://{f.as_posix()}"))
    g = pd.concat(frames, ignore_index=True)
    g["geoid"] = g["GEO_ID"].str.split("US").str[-1]
    g = g[g["geoid"].str[:2].isin(fips)]
    return gpd.GeoDataFrame(g[["geoid", "geometry"]], geometry="geometry", crs=frames[0].crs)


def cache_note() -> str:
    return f"Census tables cached in `{BENCH.relative_to(paths.REPO_ROOT)}/`."


