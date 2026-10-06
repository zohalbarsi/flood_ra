"""Machine-specific data locations.

Every script gets data paths from here, never from hard-coded strings, so the
same code runs on the remote desktop and anywhere else. Paths come from
config/paths.yaml (gitignored); an environment variable FLOOD_RA_<KEY> overrides
any entry, e.g. FLOOD_RA_INFOUSA_RAW.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

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
INFOUSA_GLOB = CFG.get("infousa_glob", "**/*.csv")
INFOUSA_DELIM = CFG.get("infousa_delim", ",")

# Standard layout of derived outputs
INFOUSA_PARQUET = DERIVED / "infousa_parquet"   # one file per raw file/year
FLOOD_CLEAN = DERIVED / "flood_clean"
MERGED = DERIVED / "merged"

for d in (DERIVED, INFOUSA_PARQUET, FLOOD_CLEAN, MERGED, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)


def require(*dirs: Path) -> None:
    """Stop with a clear message if an input folder does not exist."""
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        sys.exit(f"folder not found: {', '.join(missing)}\nfix the path in {CONFIG_FILE}")
