# Shanghai 15MC Prototype

This folder is a working baseline for the **15-Minute Shanghai** brief. It is not the final
five-week submission, but it gives you a coherent starting point with:

- a processed H3 seed dataset derived from the files already available in this thread
- a processed 500 m grid dataset plus H3 aggregation derived from the files already available in this thread
- three notebook files aligned with the brief structure
- a lightweight local web application for exploring the current H3 outputs

## Structure

- `notebooks/01_data_collection.ipynb`
- `notebooks/02_grid_isochrones.ipynb`
- `notebooks/03_scoring_h3.ipynb`
- `data/processed/shanghai_grid_seed.geojson`
- `data/processed/shanghai_grid_seed.json`
- `data/processed/shanghai_h3_seed.geojson`
- `data/processed/project_manifest.json`
- `AI_ASSISTANCE.md`
- `DEPLOYMENT_NOTES.md`
- `TRELLO_BOARD_TEMPLATE.md`
- `docs/DELIVERY_EVIDENCE.md`
- `app/`
- `scripts/`

## Current Prototype Choices

- **Track focus:** `Track A — Healthy Lifestyle & Sport`
- **GitHub repository:** `https://github.com/usera3/shanghai-15mc`
- **Public app:** `https://usera3.github.io/shanghai-15mc/`
- **Trello board:** `https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi`
- **Hex resolution:** `H3 r8`
- **Current accessibility logic:** grid-first metrics at `500 m` cell scale, walk / bike road-network
  nearest-amenity access, and proxy transit / car surfaces before aggregation to H3
- **Environmental layers:** AQI and Sentinel-2 NDVI proxies are attached to the grid and H3 outputs
- **Housing quality control:** H3 cells without Anjuke housing samples are flagged as `no housing sample`
  instead of being treated as low-cost areas
- **Data transparency:** `project_manifest.json` records provenance, collection-date notes, scoring logic,
  Track A indicator coverage, speed assumptions, and limitations without exposing local absolute paths
- **Delivery evidence:** `docs/DELIVERY_EVIDENCE.md` collects external links, screenshots, Trello structure,
  verification notes, and data scale checks
- **Missing for a final submission:** true 15-minute network isochrones for walk / bike / transit / car
  and GTFS integration for transit frequency

## Raw Sources Used

- `UTSEUS-anjuke-real-estate.csv`
- decompressed classified CSVs from `POI 2024.zip`
- `shanghai-roads-simplified.parquet`
- Shanghai municipal boundary from Aliyun DataV GeoAtlas

The current prototype uses the extracted `POI 2024` classified CSV files as its main amenity layer.
Type-based filters are documented in:

- `data/processed/poi_2024_probe.json`
- `data/processed/poi_2024_mapping_notes.md`

It now also produces a **grid-first analytical layer**:

- `data/processed/shanghai_grid_seed.json`
- `data/processed/shanghai_grid_seed.geojson`

That grid layer is the closest local equivalent to the course requirement for a documented
500 m grid prior to H3 aggregation.

Environmental layers are cached in:

- `data/processed/shanghai_environment_layers.json`

AI assistance is disclosed in:

- `AI_ASSISTANCE.md`

Static deployment notes and a Trello board template are provided in:

- `DEPLOYMENT_NOTES.md`
- `TRELLO_BOARD_TEMPLATE.md`
- `docs/DELIVERY_EVIDENCE.md`

The public-facing app uses a lightweight Canvas H3 renderer so the 14k-cell local prototype remains
usable in the browser.

Walk and bike scores now include a cached road-network nearest-amenity layer:

- `data/processed/shanghai_network_accessibility_grid.json`

## How To Refresh

From this workspace:

```powershell
$env:PYTHONPATH=(Resolve-Path '.\pydeps')
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\build_15mc_seed.py'
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\generate_notebooks.py'
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\execute_project_notebooks.py'
```

If running from a clean shell, set `PYTHONPATH` to include `.\pydeps` first because the project uses
locally installed geospatial and notebook packages.

The lightweight local raw inputs are stored at `data/raw/anjuke_price_distance_filtered.parquet` and
`data/raw/shanghai-roads-simplified.parquet`. Very large raw POI archives are intentionally ignored; if
you move them, set `SHANGHAI_15MC_RAW_DIR` to the folder containing `POI 2024.zip` and related raw files.
You can also override `SHANGHAI_15MC_APARTMENT_PATH` or `SHANGHAI_15MC_ROADS_PATH` for custom locations.

## Run The App

```powershell
cd C:\Users\mozi\Documents\Codex\2026-05-24\files-mentioned-by-the-user-utseus\shanghai_15mc\app
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m http.server 4173
```

Then open:

- `http://127.0.0.1:4173`

## Notes

- The current "housing band" is a **sale-price proxy**, not a true rent layer.
- The notebooks are intentionally documented and structured to match the course brief, while keeping
  computation light enough for this local environment.
- Walk and bike have road-network accessibility fields, but the project still lacks full polygonal
  isochrones from a routing API and GTFS-aware transit travel times.
- The deployable app folder is `app/`; no JavaScript build step is required.
