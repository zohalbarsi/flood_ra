"""Project choices: which raw files, states and columns, and which census
columns build the merge keys. They live in config/settings.yaml, tracked in
git, so every result can be traced to the choices that produced it.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
with open(SETTINGS_FILE) as f:
    _S = yaml.safe_load(f)

INFOUSA_GLOB = _S["infousa_glob"]
INFOUSA_DELIM = _S.get("infousa_delim", ",")
INFOUSA_ENCODING = _S.get("infousa_encoding", "latin-1")
PREFER_VERSION = {int(y): str(v) for y, v in (_S.get("prefer_version") or {}).items()}
STUDY_STATES = [s.upper() for s in _S.get("study_states") or []]
DROP_COLUMNS = list(_S.get("drop_columns") or [])
FLOOD_FILES = dict(_S["flood_files"])
GEO_FAMILY = _S.get("geo_family", "census")


def year_of(name: str) -> int | None:
    """The four-digit year in a file name, e.g. 2018 in US_Consumer_5_File_2018.csv.gz."""
    m = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", name)
    return int(m.group()) if m else None
