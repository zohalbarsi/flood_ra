"""Census geography: state codes, the study states, and SQL macros that turn
the infoUSA code columns into zero-padded tract and block-group GEOIDs.
"""
from __future__ import annotations

import sys

import duckdb

from flood_ra import paths, settings

STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56", "PR": "72",
}

# infoUSA columns (state, county, tract, block group) in each candidate set
FAMILIES = {
    "census": ("GE_CENSUS_STATE_2010", "GE_CENSUS_COUNTY", "GE_CENSUS_TRACT", "GE_CENSUS_BG"),
    "als2010": ("GE_CENSUS_STATE_2010", "GE_ALS_COUNTY_CODE_2010",
                "GE_ALS_CENSUS_TRACT_2010", "GE_ALS_CENSUS_BG_2010"),
}


def study_states() -> list[str]:
    """Postal codes of the study states: settings.yaml, else the flood tract file's states."""
    if settings.STUDY_STATES:
        return settings.STUDY_STATES
    f = paths.FLOOD_EXPOSURE / settings.FLOOD_FILES["tract"]
    codes = duckdb.sql(f"SELECT DISTINCT right('00' || trim(STATEFP), 2) "
                       f"FROM read_csv('{f.as_posix()}', all_varchar=true)").fetchall()
    postal = {v: k for k, v in STATE_FIPS.items()}
    unknown = [c for (c,) in codes if c not in postal]
    if unknown:
        sys.exit(f"unknown state FIPS {unknown} in {f.name}; set study_states in config/settings.yaml")
    return sorted(postal[c] for (c,) in codes)


def define_macros(con: duckdb.DuckDBPyConnection) -> None:
    """norm_state/county/tract/bg: a raw code in any common format -> the
    zero-padded Census code, or NULL if it is not a valid code.
    Handles e.g. tract "020100", "20100", "0201.00", "201.00"; county "019",
    "19", "37019"; state "37" or "NC". right('000' || x, n) pads without
    truncating (lpad would cut long values)."""
    postal = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in STATE_FIPS.items())
    con.sql(f"""CREATE OR REPLACE MACRO norm_state(s) AS CASE
        WHEN regexp_full_match(trim(s), '[0-9]{{1,2}}') THEN right('00' || trim(s), 2)
        ELSE CASE upper(trim(s)) {postal} END END""")
    con.sql(r"""CREATE OR REPLACE MACRO norm_county(c) AS CASE
        WHEN regexp_full_match(trim(c), '[0-9]{1,5}') THEN right('000' || trim(c), 3) END""")
    # tract 000000 means unknown (Data Axle data dictionary)
    con.sql(r"""CREATE OR REPLACE MACRO norm_tract(t) AS NULLIF(CASE
        WHEN regexp_full_match(trim(t), '[0-9]{1,4}\.[0-9]{1,2}')
            THEN right('0000' || split_part(trim(t), '.', 1), 4)
                 || rpad(split_part(trim(t), '.', 2), 2, '0')
        WHEN regexp_full_match(trim(t), '[0-9]{1,6}') THEN right('000000' || trim(t), 6) END, '000000')""")
    con.sql(r"""CREATE OR REPLACE MACRO norm_bg(b) AS CASE
        WHEN regexp_full_match(trim(b), '0*[0-9]') THEN right(trim(b), 1) END""")
    # coordinates come as "035.123456", "35.12345678" or "+35.12"; 0 means missing
    for name, limit in (("parse_lat", 90), ("parse_lon", 180)):
        con.sql(f"""CREATE OR REPLACE MACRO {name}(x) AS CASE
            WHEN TRY_CAST(trim(x) AS DOUBLE) BETWEEN -{limit} AND {limit}
                 AND TRY_CAST(trim(x) AS DOUBLE) != 0 THEN TRY_CAST(trim(x) AS DOUBLE) END""")


# SQL for a household's coordinates as numbers (needs define_macros)
LATITUDE = 'parse_lat("GE_LATITUDE_2010")'
LONGITUDE = 'parse_lon("GE_LONGITUDE_2010")'


def tract_geoid(family: str) -> str:
    """SQL for the 11-digit tract GEOID from one set of infoUSA columns."""
    s, c, t, _ = FAMILIES[family]
    return f'(norm_state("{s}") || norm_county("{c}") || norm_tract("{t}"))'


def bg_geoid(family: str) -> str:
    """SQL for the 12-digit block-group GEOID (tract GEOID + block group digit)."""
    return f'({tract_geoid(family)} || norm_bg("{FAMILIES[family][3]}"))'
