# flood_ra

Merge of infoUSA business records with flood exposure data.

## How code and data are split

- **Code** lives in this git repo. Write and edit it anywhere, then push.
- **Data** stays on the server and is never committed (`.gitignore` blocks
  csv/dta/parquet/etc.). Scripts find it through `config/paths.yaml`, a
  file on each machine that git does not track.
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

| step | script | output (on server, under `derived`) |
|---|---|---|
| 00 | `scripts/00_inspect_raw.py` | `output/logs/data_inventory.md`: schema only, safe to commit |
| 01 | `scripts/01_infousa_to_parquet.py` | `infousa_parquet/*.parquet`: one per raw file, all text columns |
| 02 | `scripts/02_flood_clean.py` | `flood_clean/*.parquet` |
| 03 | `scripts/03_merge.py` | `merged/infousa_flood.parquet` + `output/logs/merge_report.txt` |

`python run_all.py` runs everything; `python run_all.py 02` starts at step 02.
Step 01 skips files it already converted (`--overwrite` to redo).

Raw inputs are read-only: the pipeline never writes into `infousa_raw` or
`flood_exposure`.

## Licensing

infoUSA / Data Axle data is licensed. Commit only code and aggregate logs
(schemas, counts, match rates), never record-level rows.
