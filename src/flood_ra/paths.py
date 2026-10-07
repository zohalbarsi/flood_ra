"""Machine-specific data locations and resources.

Every script gets data paths from here, never from hard-coded strings, so the
same code runs on the remote desktop and anywhere else. Values come from
config/paths.yaml (gitignored); an environment variable FLOOD_RA_<KEY>
overrides any entry, e.g. FLOOD_RA_INFOUSA_RAW.
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from flood_ra import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO_ROOT / "config" / "paths.yaml"
LOG_DIR = REPO_ROOT / "output" / "logs"


def _load() -> dict:
    if not CONFIG_FILE.exists():
        sys.exit(f"{CONFIG_FILE} not found. Run: "
                 "cp config/paths.example.yaml config/paths.yaml")
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f) or {}
    for key in list(cfg):
        env = os.environ.get(f"FLOOD_RA_{key.upper()}")
        if env:
            cfg[key] = env
    return cfg


CFG = _load()
INFOUSA_RAW = Path(CFG["infousa_raw"]).expanduser()
FLOOD_EXPOSURE = Path(CFG["flood_exposure"]).expanduser()
DERIVED = Path(CFG["derived"]).expanduser()

# Files converted at once, and DuckDB threads / memory per file
PARALLEL = int(CFG.get("parallel_files", 4))
THREADS = int(CFG.get("duckdb_threads", 2))
MEMORY = str(CFG.get("duckdb_memory", "4GB"))

# Standard layout of derived outputs
INFOUSA_PARQUET = DERIVED / "infousa_parquet"   # one file per year (and version)
FLOOD_CLEAN = DERIVED / "flood_clean"
MERGED = DERIVED / "merged"
DUCKDB_TMP = DERIVED / "duckdb_tmp"

for d in (DERIVED, INFOUSA_PARQUET, FLOOD_CLEAN, MERGED, DUCKDB_TMP, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)


def infousa_parquet(year: int, version: str = "main") -> Path:
    """Converted file for one year; versions other than main get a suffix."""
    suffix = "" if version == "main" else f"_{version}"
    return INFOUSA_PARQUET / f"infousa_{year}{suffix}.parquet"


def converted_versions() -> dict[int, dict[str, Path]]:
    """{year: {version: file}} for every file step 01 has converted."""
    out = defaultdict(dict)
    for p in INFOUSA_PARQUET.glob("infousa_*.parquet"):
        m = re.fullmatch(r"infousa_(\d{4})(?:_(.+))?\.parquet", p.name)
        if m:
            out[int(m.group(1))][m.group(2) or "main"] = p
    return dict(sorted(out.items()))


def chosen_files() -> dict[int, Path]:
    """Converted file per year: the version settings.yaml prefers, else main."""
    files = {}
    for year, versions in converted_versions().items():
        want = settings.PREFER_VERSION.get(year, "main")
        if want in versions:
            files[year] = versions[want]
        else:
            print(f"warning: {year} has no '{want}' version; skipped")
    return files


def require(*dirs: Path) -> None:
    """Stop with a clear message if an input folder does not exist."""
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        sys.exit(f"folder not found: {', '.join(missing)}\nfix the path in {CONFIG_FILE}")
