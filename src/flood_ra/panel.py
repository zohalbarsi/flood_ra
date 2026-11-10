"""Shared pieces of the household panel (steps 07 and 08): where its files
live, which columns it keeps, and how panel households are found in a file.

Panel households: every FAMILYID that is a primary family in a study state
in at least one analysis year. Panel adults: every IndividualID ever listed
in a panel household's records there. Everything in derived/panel/ is record
level and stays on the server.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from flood_ra import paths, settings

DIR = paths.DERIVED / "panel"
SLICES = 8  # large steps run in this many slices of households, so they fit in memory
NATIONAL = DIR / "national"              # panel records outside the study states (step 07)
WORK = DIR / "work"                      # step 08 intermediates, removed when it finishes
IDS_FAMILY = DIR / "ids_family.parquet"  # FAMILYIDs of panel households
IDS_PERSON = DIR / "ids_person.parquet"  # adults ever listed in a panel household

PERSON_SLOTS = [f"IndividualID_{k}" for k in range(1, 6)]
# columns kept from each record (names, ages and the other people's codes are left out)
COLUMNS = [
    "FAMILYID", "LOCATIONID", "PRIMARY_FAMILY_IND", "RECENCY_DATE", "STATE", "ZIP",
    "HOUSE_NUM", "STREET_PRE_DIR", "STREET_NAME", "STREET_SUFFIX", "STREET_POST_DIR", "UNIT_NUM",
    "BOX_TYPE", "BOX_NUM", "ROUTE_TYPE", "ROUTE_NUM",
    "GE_CENSUS_STATE_2010", "GE_ALS_COUNTY_CODE_2010", "GE_ALS_CENSUS_TRACT_2010", "GE_ALS_CENSUS_BG_2010",
    "GE_CENSUS_LEVEL_2010", "LOCATION_TYPE",
    "OWNER_RENTER_STATUS", "FIND_DIV_1000", "WEALTH_FINDER_SCORE", "ESTMTD_HOME_VAL_DIV_1000",
    "CHILDREN_IND", "CHILDRENHHCOUNT", "HEAD_HH_AGE_CODE", "MARITAL_STATUS", "LENGTH_OF_RESIDENCE",
    "Ethnicity_Code_1", *PERSON_SLOTS,
]


def national_file(year: int) -> Path:
    return NATIONAL / f"infousa_{year}.parquet"


def persons_list(cols) -> str:
    """SQL list of a record's adults (trimmed IndividualIDs; NULL for an empty slot)."""
    slots = [c for c in PERSON_SLOTS if c in cols]
    return "[" + ", ".join(f"nullif(trim({c}), '')" for c in slots) + "]" if slots else "[]::VARCHAR[]"


def panel_records(select: str, cols, fam: str, per: str) -> str:
    """SQL keeping the rows of `select` (a query with the record columns) that
    belong to the panel: FAMILYID in `fam`, or any adult in `per` (both are
    one-column queries named id). A record matched by FAMILYID passes once;
    the others are unnested by adult and matched against `per`, so each ID
    list is held in memory once. A record matched through two of its adults
    comes out twice; step 08 keeps one row per household and year anyway."""
    return f"""
        WITH m AS (SELECT r.*, trim(r.FAMILYID) IN (SELECT id FROM {fam}) AS _fam FROM ({select}) r),
             u AS (SELECT m.*, unnest(CASE WHEN _fam THEN [NULL::VARCHAR] ELSE {persons_list(cols)} END) AS _p
                   FROM m)
        SELECT * EXCLUDE (_fam, _p) FROM u WHERE _fam OR _p IN (SELECT id FROM {per})
    """


def ids_signature(files: dict[int, Path], states: list[str]) -> str:
    """What the panel IDs depend on: the study states and the converted files."""
    return json.dumps({"states": sorted(states), "last_year": settings.LAST_YEAR,
                       "files": {str(y): [f.name, f.stat().st_size, int(f.stat().st_mtime)]
                                 for y, f in sorted(files.items())}}, sort_keys=True)


def stored(path: Path) -> str | None:
    """The signature a panel file was written with (None if absent)."""
    if not path.exists():
        return None
    rows = duckdb.sql("SELECT decode(key), decode(value) "
                      f"FROM parquet_kv_metadata('{path.as_posix()}')").fetchall()
    return dict(rows).get("flood_ra_panel")


def metadata(sig: str) -> str:
    """COPY option that stores a signature in a Parquet file."""
    return "KV_METADATA {flood_ra_panel: '" + sig.replace("'", "''") + "'}"
