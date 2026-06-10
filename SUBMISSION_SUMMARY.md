# Submission Summary

This file is a marker-facing guide to the Shanghai 15MC submission package. It points each major
assignment requirement to the evidence that proves it has been addressed.

## Project Links

| Item | Evidence |
|---|---|
| GitHub repository | https://github.com/usera3/shanghai-15mc |
| Public app | https://usera3.github.io/shanghai-15mc/ |
| Trello board | https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi |
| Public manifest | https://usera3.github.io/shanghai-15mc/data/project_manifest.json |

## Requirement Evidence Map

| Requirement area | Evidence in this submission |
|---|---|
| Public GitHub repository | Repository link above, GitHub Pages workflow in `.github/workflows/deploy-pages.yml`, screenshot in `docs/screenshots/github-repository.png` |
| Public interactive web app | `app/` static site, deployed URL above, screenshot in `docs/screenshots/public-app-map.png` |
| Trello planning board | Trello board link above, board structure in `docs/DELIVERY_EVIDENCE.md`, screenshots in `docs/screenshots/` |
| Documented data collection | `notebooks/01_data_collection.ipynb`, `data/processed/poi_2024_mapping_notes.md`, and source provenance in `project_manifest.json` |
| 500 m grid workflow | `notebooks/02_grid_isochrones.ipynb` and `data/processed/project_manifest.json` record the 33,021-cell grid |
| H3 aggregation | `notebooks/03_scoring_h3.ipynb` and `app/data/shanghai_h3_seed_min.json` contain 14,641 H3 r8 cells |
| Track focus | Track A, Healthy Lifestyle & Sport, documented in notebooks, manifest, app, and README |
| Mode-specific accessibility | Walk, bike, transit, and car score fields are present in the app payload and manifest |
| Data transparency | `app/data/project_manifest.json`, the public app transparency panel, and `docs/DELIVERY_EVIDENCE.md` |
| AI assistance disclosure | `AI_ASSISTANCE.md` |
| Local validation | `scripts/validate_delivery.py` checks app, data, manifest, notebooks, screenshots, docs, and optional public URLs |

## What The App Demonstrates

- Zoomable Leaflet / OpenStreetMap basemap with a Canvas H3 overlay.
- Four transport modes: walk, bike, transit, and car.
- Three score layers: baseline, Track A, and composite.
- Clickable hex detail panel with amenity, housing, transit, environmental, and score metrics.
- Adjustable "Where To Live" recommender with top-10 highlighting.
- Data transparency panel with source provenance, scoring method, speed assumptions, platform links, and limitations.

## Method Positioning

The project is intentionally transparent about what is complete and what remains a proxy. It builds a
grid-first 500 m analytical layer, aggregates to H3 r8, and improves walk/bike scoring with cached
road-network nearest-amenity access. Transit and car remain proxy surfaces, and the project does not
claim full routing-engine isochrones or GTFS-aware transit travel times.

## Verification

Run these checks from the repository root:

```powershell
python .\scripts\validate_delivery.py
python .\scripts\validate_delivery.py --online
```
