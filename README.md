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
When a pull changes `requirements.txt`, run `pip install -r requirements.txt` first.

## Pipeline

| step | script | output (under `derived` on the server) | log (safe to commit) |
|---|---|---|---|
| 00 | `00_inspect_raw.py` | none | `data_inventory.md`: files and columns |
| 01 | `01_infousa_to_parquet.py` | `infousa_parquet/infousa_<year>[_alt].parquet` | `infousa_conversion.txt` |
| 02 | `02_flood_clean.py` | `flood_clean/flood_{tract,bg,block}.parquet`, `block_polygons.parquet` | `flood_clean.md` |
| 03 | `03_assign_blocks.py` | `geo/point_blocks.parquet` | `block_assignment.md` |
| 04 | `04_merge.py` | `merged/infousa_flood_<year>.parquet` | `merge_report.md` |
| 05 | `05_describe_sample.py` | none | `sample_report.md` |

- **01** reads each yearly `.csv.gz` in place, keeps households whose address
  state is a study state (`study_states` in settings.yaml), keeps all
  columns, names included (`drop_columns` can drop some), as text so codes
  keep leading zeros. It
  converts several files at once, checks each with `gzip -t` (a truncated
  file fails instead of becoming a partial year), and counts rejected rows by
  error type. Each converted file records the settings it was made with;
  re-runs skip files whose settings still match and redo the rest.
- **02** builds zero-padded GEOIDs for each flood file and prefixes the flood
  measures by level (`tract_pct_flooded_gfd`, `bg_pct_flooded_gfd`, ...).
  It also turns the block `.geojson` into outlines in WGS84
  longitude/latitude, whatever coordinate system the file uses.
- **03** places each household in a 2010 census block: infoUSA has no block
  code, so it finds the block outline containing the household's
  coordinates (point in polygon, once per distinct coordinate across all
  years). Its report checks the blocks against the households' tract and
  block-group codes, by geocode level.
- **04** builds tract and block-group GEOIDs from the infoUSA census columns
  and left-joins the tract, block-group and block flood measures, plus
  `block_geoid`, numeric `latitude`/`longitude` and `in_flood_counties`
  (outside those counties the flood measures are missing, not zero). Its
  report gives match rates under both census column sets.
- **05** describes the household records to guide sample restrictions:
  version comparison, families per address, year-to-year continuity,
  record-status flags, geocode precision, record recency and code formats.

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

- **Study area: North and South Carolina.** The flood data cover 34 NC
  counties only (34-38% of NC households live in them). SC households are
  kept as a comparison group and so that families moving between NC and SC
  are followed; they have no flood measures (`in_flood_counties` is false).
- **Merge key: `GE_ALS_*_2010` columns**, the Census 2010 geography in the
  data dictionary. They match 100% of tracts and block groups in every year.
  The `GE_CENSUS_*` columns are Census 2000 geography (hence the ~43% match in
  2007-2017) and are empty from 2018 on. Tract `000000` means unknown and is
  treated as missing.
- **Block level: built** from household coordinates (no block code in
  infoUSA). 99.7-99.9% of households in the flood counties fall in a block.
  For geocode level `P` the block lies in the household's census tract
  99-100% of the time.
- **2023: `alt/` version**: the same families as main, identical on every
  shared column, plus title, age and gender. **2024: main**: both versions
  have the same families, but `alt/` has no ages, a coarser ethnicity coding,
  and different gender, latitude and person IDs.

## Open questions

- **Sample definition.** The file has more records than NC has households
  (4.4M in 2007, 7.8M in 2025). Per the data dictionary, `LOCATIONID` links a
  primary family with its subfamilies, so a `LOCATIONID` is a household and
  `PRIMARY_FAMILY_IND = 1` marks its primary family: about one per address,
  3.77M in 2010 against 3.75M households in the 2010 Census. The subfamilies
  grow from 14% to 39% of records, far above Census subfamily rates;
  `sample_report.md` checks whether their adults are also listed in the
  primary family. Candidates to drop for location-based exposure:
  `VACANT = 1`, `USPSNOSTATS = 1`, PO boxes (`ADDRESSTYPE = P`), nursing and
  retirement homes (`LOCATION_TYPE` N, R) and coarse geocodes
  (`GE_CENSUS_LEVEL_2010` other than `P`; the dictionary gives no codes for
  this field).
- **Movers and attrition.** Of each year's primary families, 82-91% appear
  the next year under the same FAMILYID (5-8% at a new NC address) and 9-18%
  do not, more than out-of-state moves explain. Only 3-5% of the missing
  families' first person reappears under another FAMILYID, so most of the
  loss is records leaving the file, not re-keying: "not found" should not be
  read as "moved away". (These figures are from the NC-only run; with SC
  added, moves between NC and SC are followed. Moves to other states still
  look like attrition.)
- **Baseline year.** Florence hit in September 2018; whether the 2018 file
  shows pre- or post-storm addresses depends on when it was compiled.
- **Geocode precision for the block merge.** A household's block is only as
  good as its coordinates. For levels other than `P` (10-20% of records) the
  block agrees with the tract code only 72-83% of the time in 2007-2019
  (97-99% from 2020, where codes and coordinates likely come from the same,
  possibly coarse, geocode). Use block exposure for level `P`; for the other
  levels prefer tract or block-group exposure, or drop them.

## Codebook notes (Data Axle data dictionary)

- `HEAD_HH_AGE_CODE`: A <25, B 25-29, ... I 60-64, **J 65+ (inferred)**,
  K 65-69, L 70-74, M 75+ (reported). J is an age band, not a missing code.
- `OWNER_RENTER_STATUS`: 9 reported owner, 7-8 likely owner, **4-6 unknown**,
  1-3 likely renter, 0 reported renter. `MARITAL_STATUS`: 0 reported single,
  1 inferred single, 2-4 modeled single, 5-6 modeled married, 7-8 inferred
  married, 9 reported married.
- `WEALTH_FINDER_SCORE` (0-9999), `FIND_DIV_1000` (income, 5-500),
  `PPI_DIV_1000` and `ESTMTD_HOME_VAL_DIV_1000` (5-9999) are in **$
  thousands**, top-coded. Home value is chosen per `LOCATIONID` and copied to
  every family there.
- `HOUSEHOLDSTATUS`: F fulfillment, S current but not fulfilled, I inactive,
  M moved out. The files hold only F and S, so all records are current.
  `DOWNGRADE_REASON_CODE` non-blank = suppressed (not mailable).
- `LOCATION_TYPE`: S single-family, M multi-family, T trailer, N nursing
  home, R retirement home, U undefined. `ADDRESSTYPE`: S house number and
  street, P PO box, R route and box, D route only, F street only, G general
  delivery.
- `RECENCY_DATE`: last confirmation at this address (YYYYMM).
  `LENGTH_OF_RESIDENCE`: years at the current address, which can flag recent
  movers.

## Licensing

infoUSA / Data Axle data is licensed. Commit only code and aggregate logs
(schemas, counts, match rates), never record-level rows. The converted and
merged files keep names and addresses; they stay on the server.
