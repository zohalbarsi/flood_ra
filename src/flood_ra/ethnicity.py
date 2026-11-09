"""Race and ethnicity from Ethnicity_Code_1, in two layers.

1. config/ethnicity_codes.csv gives each Data Axle ethnicity code its Data Axle
   ethnic group letter. The codes are mostly ISO country codes. The 168 codes
   cover every code in the NC and SC files for 2007-2025. Every value is read
   as text: "NA" is Namibia, not a missing value, and "00" is a code, not the
   number 0.
2. The project's categories sit on top of the groups (the Stata
   classification), with one change: LR counts as Black American. LR was the
   main code of Black households until 2017. In 2018 Data Axle replaced it
   with Q6-Q9.

Group letters:
- W Western European; S Scandinavian; J Jewish; M Mediterranean; E Eastern
  European.
- B African and African American.
- H Hispanic (H5), Portuguese (PT) and Basque (B3).
- F East and Southeast Asian; A South Asian; C Central and Southwest Asian.
- P Pacific, including the Philippines.
- I Middle Eastern and North African.
- N Native American.
- X other: Australia, New Zealand, Suriname, Guyana, Maldives.
- Z unknown: 00 and ZZ.
"""
from __future__ import annotations

import csv
import sys
from functools import lru_cache
from pathlib import Path

CODES_FILE = Path(__file__).resolve().parents[2] / "config" / "ethnicity_codes.csv"

UNKNOWN = "Unknown"        # group Z (00, ZZ) or a blank code
NOT_PLACED = "Not placed"  # no rule places the code: GY, MV, or a code missing from the table
BLANK = "(blank)"          # label of a blank code in tables

BLACK_AMERICAN = ("B5", "LR", "Q6", "Q7", "Q8", "Q9")

# categories in table order, and the broad group of each (the race_* indicators)
CATEGORIES = {
    "White": "white", "Ethnic White": "white",
    "Black American": "black", "Other Black": "black",
    "Hispanic": "hispanic",
    "East Asian": "asian", "South Asian": "asian",
    "Pacific": "pacific", "MENA": "mena", "American Indian": "native", "Other": "other",
}
BROAD_GROUPS = ["white", "black", "hispanic", "asian", "pacific", "mena", "native", "other"]


@lru_cache(maxsize=1)
def load_codes() -> dict[str, str]:
    """Ethnicity code -> Data Axle group letter, from config/ethnicity_codes.csv."""
    if not CODES_FILE.exists():
        sys.exit(f"{CODES_FILE} not found: it holds the ethnicity code table (columns code,group)")
    with open(CODES_FILE, newline="", encoding="utf-8") as f:
        rows = [(r["code"].strip().upper(), r["group"].strip().upper()) for r in csv.DictReader(f)]
    codes = dict(rows)
    if len(codes) != len(rows):
        raise ValueError(f"{CODES_FILE.name}: a code is listed twice")
    bad = sorted(c for c, g in codes.items() if not c or len(g) != 1)
    if bad:
        raise ValueError(f"{CODES_FILE.name}: rows without a one-letter group: {bad}")
    return codes


def category(code: str | None) -> str:
    """Category of one code. The rules run in the Stata order, so a later rule
    overrides an earlier one (in practice no two rules match the same code)."""
    c = (code or "").strip().upper()
    g = load_codes().get(c, "")
    cat = UNKNOWN if g == "Z" or c == "" else NOT_PLACED
    if c in BLACK_AMERICAN:
        cat = "Black American"
    if g == "B" and c not in BLACK_AMERICAN:
        cat = "Other Black"
    if g == "F":
        cat = "East Asian"
    if g == "A":
        cat = "South Asian"
    if g == "P":
        cat = "Pacific"
    if c == "H5":
        cat = "Hispanic"
    if g in ("W", "S") or c in ("AU", "NZ"):
        cat = "White"
    if g in ("J", "M", "E"):
        cat = "Ethnic White"
    if g == "H" and c != "H5":
        cat = "Ethnic White"
    if g == "I":
        cat = "MENA"
    if g == "N":
        cat = "American Indian"
    if g == "C" or c == "SR":
        cat = "Other"
    return cat


def group(code: str | None) -> str:
    """Data Axle group letter of a code ("" if blank or not in the table)."""
    return load_codes().get((code or "").strip().upper(), "")


def broad(code: str | None) -> str | None:
    """Broad group (white, black, hispanic, asian, pacific, mena, native, other);
    None for Unknown and Not placed, which are left out of every share."""
    return CATEGORIES.get(category(code))


def sql_broad(column: str) -> str:
    """SQL expression for the broad group of a text column (NULL if Unknown or
    Not placed)."""
    whens = [f"WHEN '{c}' THEN '{b}'" for c in sorted(load_codes()) if (b := broad(c))]
    return f"(CASE upper(trim({column})) {' '.join(whens)} END)"
