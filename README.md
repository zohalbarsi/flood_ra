# flood_ra

Merge of infoUSA (Data Axle) Consumer household records, 2007-2025, with
Hurricane Florence (2018) flood exposure by census tract, block group and block.

## How code and data are split

- **Code** lives in this git repo. Write and edit it anywhere, then push.
- **Data** stays on the server and is never committed (`.gitignore` blocks
  csv/dta/parquet/etc.). Scripts find it through `config/paths.yaml`, a
  file on each machine that git does not track.
- **Project choices** (which raw files, states, columns, merge keys) live in
  `config/settings.yaml`, which *is* tracked, so every result can be traced
  to the settings that produced it.
- The pipeline **runs on the remote desktop**, next to the data:
  `git pull` brings in the latest code, then `python run_all.py`.

## One-time setup on the remote desktop

Needs Python 3.9+ (`python3 --version`; on a cluster you may need
`module load python` first). Data paths are already filled in for this server
in `config/paths.example.yaml`:

| data | server folder |
|---|---|
| infoUSA raw | `/home/z/zebarsi/Desktop/project/InfoUSA/rawdata` |
| flood exposure | `/home/z/zebarsi/Desktop/RA/flood_exposure` |
| pipeline output | `/home/z/zebarsi/Desktop/RA/flood_ra_derived` |

```bash
cd ~/Desktop/RA
git clone https://github.com/zohalbarsi/flood_ra.git
cd flood_ra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/paths.example.yaml config/paths.yaml   # edit if a path above is wrong
python scripts/00_inspect_raw.py                  # writes output/logs/data_inventory.md
git add output/logs/data_inventory.md && git commit -m "Add data inventory" && git push
```

If the repo is private, git asks for a GitHub login: use a personal access
token as the password, or set up an SSH key. If the server cannot reach
GitHub at all, copy the code over by zip/shared drive and send back the
inventory file the same way.

Each later session: `source .venv/bin/activate && git pull && python run_all.py`.

## Pipeline

| step | script | output (under `derived` on the server) | log (safe to commit) |
|---|---|---|---|
| 00 | `00_inspect_raw.py` | none | `data_inventory.md`: files and columns |
| 01 | `01_infousa_to_parquet.py` | `infousa_parquet/infousa_<year>[_alt].parquet` | `infousa_conversion.txt` |
| 02 | `02_flood_clean.py` | `flood_clean/flood_{tract,bg,block}.parquet` | `flood_clean.md` |
| 03 | `03_merge.py` | `merged/infousa_flood_<year>.parquet` | `merge_report.md` |
| 04 | `04_describe_sample.py` | none | `sample_report.md` |

- **01** reads each yearly `.csv.gz` in place, keeps households whose address
  state is a study state (default: the states in the flood data), drops the
  name columns, and keeps every column as text so codes keep leading zeros.
  It converts several files at once, checks each with `gzip -t` (a truncated
  file fails instead of becoming a partial year), skips files already done,
  and counts rejected rows by error type.
- **02** builds zero-padded GEOIDs for each flood file and prefixes the flood
  measures by level (`tract_pct_flooded_gfd`, `bg_pct_flooded_gfd`, ...).
- **03** builds tract and block-group GEOIDs from the infoUSA census columns
  and left-joins the tract and block-group flood measures, plus
  `in_flood_counties` (outside those counties the flood measures are missing,
  not zero). Its report gives match rates under both census column sets.
- **04** describes the household records to guide sample restrictions:
  version comparison, families per address, record-status flags, geocode
  precision, record recency and code formats.

Logs are written to `output/logs/`. Step 01 is the slow one (19 years plus 2
alternate versions, about 275 GB compressed): expect several hours. Run it in
the background so a closed window doesn't stop it:

```bash
nohup python run_all.py 01 > ~/flood_ra_run.log 2>&1 &
tail -f ~/flood_ra_run.log          # watch progress; Ctrl-C stops watching only
```

If it stops, run the same command again: finished years are skipped.
`parallel_files` in `config/paths.yaml` sets how many files run at once
(default 4).

Read the merged years together, e.g. in Python
`duckdb.sql("SELECT * FROM read_parquet('<derived>/merged/*.parquet', union_by_name=true)")`
or in R `arrow::open_dataset("<derived>/merged", unify_schemas = TRUE)`.

Raw inputs are read-only: the pipeline never writes into `infousa_raw` or
`flood_exposure`.

## Decisions so far (config/settings.yaml)

- **Study area: North Carolina.** The flood data cover 34 NC counties only,
  so step 01 keeps NC households (34-38% of them live in those counties).
- **Merge key: `GE_ALS_*_2010` columns.** They match 100% of tracts and block
  groups in every year. The `GE_CENSUS_*` columns match ~43% in 2007-2017
  (another tract vintage) and are empty from 2018 on.
- **2023: `alt/` version**: the same families as main, identical on every
  shared column, plus title, age and gender. **2024: main for now**: both
  versions have the same families but differ in some columns (see
  `sample_report.md`).

## Open questions

- **Sample definition.** The file has more records than NC has households
  (4.4M in 2007, 7.8M in 2025) because addresses carry extra, non-primary
  families. `PRIMARY_FAMILY_IND = 1` leaves about one family per address:
  3.77M in 2010 against 3.75M households in the 2010 Census. Candidates to
  drop for location-based exposure: `VACANT = 1`, `USPSNOSTATS = 1`, PO boxes
  (`ADDRESSTYPE = P`) and coarse geocodes (`GE_CENSUS_LEVEL_2010` other than
  `P`). Confirm the codes in the Data Axle data dictionary.
- **Movers.** Keeping only NC households drops families once they move out
  of state.
- **Baseline year.** Florence hit in September 2018; whether the 2018 file
  shows pre- or post-storm addresses depends on when it was compiled.
- **Block level.** infoUSA has no block code, so a block merge needs a
  spatial join of household coordinates to the block polygons (the
  `.geojson`); not built yet.

## Licensing

infoUSA / Data Axle data is licensed. Commit only code and aggregate logs
(schemas, counts, match rates), never record-level rows.
