"""Step 0: inventory the raw data on the server WITHOUT copying any of it.

Writes output/logs/data_inventory.md: every file in the infoUSA and
flood_exposure folders with its size, plus the delimiter, header and column
names/types of each tabular file, and the files inside each .zip.
`python scripts/00_inspect_raw.py corelogic` inventories only the folder set
as corelogic_raw in config/paths.yaml, into output/logs/corelogic_inventory.md.
`python scripts/00_inspect_raw.py folder <path>` inventories any folder into
output/logs/inventory_<folder name>.md, grouping files that differ only by
state code or digits and showing each distinct column layout once.
The reports hold no data values, so they are safe to commit and share; they
are how code written elsewhere learns the schema of data that never leaves
the server.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flood_ra import paths, settings  # noqa: E402
from flood_ra.inventory import compact_section, section  # noqa: E402


def main():
    if sys.argv[1:2] == ["folder"]:
        if len(sys.argv) != 3:
            sys.exit("usage: python scripts/00_inspect_raw.py folder <path>")
        root = Path(sys.argv[2]).expanduser().resolve()
        paths.require(root)
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
