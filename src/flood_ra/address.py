"""A household's mailing address as one key, comparable across years and
file versions (used to tell whether a household moved)."""
from __future__ import annotations


def norm(col: str, cols: set[str]) -> str:
    """SQL for one address part, upper-cased with single spaces ('' if absent)."""
    if col.startswith("left(") or col in cols:
        return f"coalesce(regexp_replace(upper(trim(CAST({col} AS VARCHAR))), '\\s+', ' ', 'g'), '')"
    return "''"


def address_key(cols: set[str], unit: bool) -> str:
    """SQL for a version-stable key (md5 hex) of a household's mailing address:
    the street address (house number, street, ZIP; optionally the unit), or for
    records without a street name the PO box or rural route and ZIP; NULL when
    neither is present."""
    zip5 = "left(trim(CAST(ZIP AS VARCHAR)), 5)"
    street = ["HOUSE_NUM", "STREET_PRE_DIR", "STREET_NAME", "STREET_SUFFIX", "STREET_POST_DIR", zip5]
    street += ["UNIT_NUM"] if unit else []
    box = ["BOX_TYPE", "BOX_NUM", "ROUTE_TYPE", "ROUTE_NUM", zip5]
    has_box = " OR ".join(f"nullif(trim(CAST({c} AS VARCHAR)), '') IS NOT NULL"
                          for c in ("BOX_NUM", "ROUTE_NUM") if c in cols) or "false"
    return (f"CASE WHEN nullif(trim(CAST(STREET_NAME AS VARCHAR)), '') IS NOT NULL "
            f"THEN md5(concat_ws('|', 'S', {', '.join(norm(c, cols) for c in street)})) "
            f"WHEN {has_box} THEN md5(concat_ws('|', 'B', {', '.join(norm(c, cols) for c in box)})) END")
