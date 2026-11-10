"""Step 0: inventory the raw data on the server WITHOUT copying any of it.
Writes output/logs/data_inventory.md: every file in the infoUSA and
flood_exposure folders with its size, plus the delimiter, header and column
names/types of each tabular file, and the files inside each .zip.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths, settings  # noqa: E402
from flood_ra.inventory import compact_section, section  # noqa: E402


USAGE = "usage: python scripts/00_inspect_raw.py [corelogic | folder <path> | <path>]"


def main():
    args = sys.argv[1:]
    if args[:1] == ["folder"] or (len(args) == 1 and args[0] != "corelogic"):
        target = args[1:2] if args[:1] == ["folder"] else args
        if len(target) != 1 or len(args) > 2:
            sys.exit(USAGE)
        root = Path(target[0]).expanduser().resolve()
        if not root.is_dir():
            sys.exit(f"folder not found: {root}\n{USAGE}")
        out = paths.LOG_DIR / f"inventory_{root.name}.md"
        out.write_text("\n".join([f"# Inventory of {root.name} (schema only, no values)", ""]
                                  + compact_section(duckdb.connect(), root.name, root,
                                                    prefer=tuple(settings.STUDY_STATES or ()))))
        print(f"wrote {out}")
        return
    if "corelogic" in sys.argv[1:]:
        if paths.CORELOGIC_RAW is None:
            sys.exit("set corelogic_raw in config/paths.yaml to the CoreLogic folder")
        paths.require(paths.CORELOGIC_RAW)
        out = paths.LOG_DIR / "corelogic_inventory.md"
        out.write_text("\n".join(["# CoreLogic inventory (schema only, no values)", ""]
                                  + section(duckdb.connect(), "CoreLogic", paths.CORELOGIC_RAW)))
        print(f"wrote {out}")
        return
    paths.require(paths.INFOUSA_RAW, paths.FLOOD_EXPOSURE)
    con = duckdb.connect()
    lines = ["# Data inventory (schema only, no values)", ""]
    lines += section(con, "infoUSA", paths.INFOUSA_RAW, settings.INFOUSA_GLOB)
    lines += section(con, "flood_exposure", paths.FLOOD_EXPOSURE)
    out = paths.LOG_DIR / "data_inventory.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
