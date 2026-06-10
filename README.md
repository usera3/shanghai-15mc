# Shanghai 15MC Submission Prototype

This repository is a submission-ready prototype package for the **15-Minute Shanghai** brief. It
prioritizes the required external deliverables, documented analysis workflow, and transparent method
limitations while also providing an interactive public app:

- a processed H3 dataset derived from the available Shanghai source files
- a processed 500 m grid workflow plus H3 aggregation
- three documented notebooks aligned with the brief structure
- a lightweight web application for exploring H3 outputs on a zoomable basemap
- delivery evidence for GitHub, GitHub Pages, Trello, screenshots, AI disclosure, and validation

## Structure

- `SUBMISSION_SUMMARY.md`
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
- **Submission summary:** `SUBMISSION_SUMMARY.md` maps the assignment-facing requirements to concrete evidence
- **Delivery evidence:** `docs/DELIVERY_EVIDENCE.md` collects external links, screenshots, Trello structure,
  verification notes, and data scale checks
- **Known method gaps:** true 15-minute network isochrones for walk / bike / transit / car
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

The public-facing app uses a Leaflet / OpenStreetMap basemap with a lightweight Canvas H3 overlay,
so the 14k-cell local prototype remains zoomable, pannable, and usable in the browser. The app also
supports clickable top-10 recommendation cards, H3 popup summaries, and an overlay-opacity control
for balancing the real basemap against the score surface.

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

## Validate The Delivery

Run the local evidence checks before submission:

```powershell
python .\scripts\validate_delivery.py
```

To also verify the published GitHub, GitHub Pages, public manifest, and Trello URLs:

```powershell
python .\scripts\validate_delivery.py --online
```

## Notes

- The current "housing band" is a **sale-price proxy**, not a true rent layer.
- The notebooks are intentionally documented and structured to match the course brief, while keeping
  computation light enough for this local environment.
- Walk and bike have road-network accessibility fields, but the project still lacks full polygonal
  isochrones from a routing API and GTFS-aware transit travel times.
- The deployable app folder is `app/`; no JavaScript build step is required.
