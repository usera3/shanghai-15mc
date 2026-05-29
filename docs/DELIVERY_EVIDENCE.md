# Delivery Evidence

This file records the external-platform and visual evidence for the Shanghai 15MC submission.

## Submission Links

| Item | Link | Status |
|---|---|---|
| GitHub repository | https://github.com/usera3/shanghai-15mc | Published on `main` |
| Public app | https://usera3.github.io/shanghai-15mc/ | GitHub Pages deployment verified |
| Trello board | https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi | Board created and instructor invited |
| Public manifest | https://usera3.github.io/shanghai-15mc/data/project_manifest.json | Records repo, deployment, and Trello links |

## Evidence Screenshots

| Evidence | File |
|---|---|
| GitHub repository landing page | `docs/screenshots/github-repository.png` |
| Public H3 map app | `docs/screenshots/public-app-map.png` |
| Trello board, Backlog and Sprint 1 side | `docs/screenshots/trello-board-backlog-sprint1.png` |
| Trello board, Sprint 2 through Blocked side | `docs/screenshots/trello-board-sprints-done-blocked.png` |
| Trello board after required list creation, before card fill | `docs/screenshots/trello-board-all-lists-empty-before-card-fill.png` |
| Trello card with image cover and screenshot attachments | `docs/screenshots/trello-card-image-attachments-visible.png` |
| Trello board showing screenshot card cover in Sprint 5 | `docs/screenshots/trello-board-card-cover-visible.png` |

## Trello Board Structure

Board name: `15MC Shanghai - Mozi`

Open lists and final card counts:

| List | Cards | Purpose |
|---|---:|---|
| Backlog | 1 | Project setup and platform requirements |
| Sprint 1 - Week 1 | 2 | Literature review and local environment |
| Sprint 2 - Week 2 | 3 | POI, 500 m grid, and housing proxy processing |
| Sprint 3 - Week 3 | 3 | Network accessibility, AQI / NDVI, and H3 aggregation |
| Sprint 4 - Week 4 | 2 | Interactive app and recommender |
| Sprint 5 - Week 5 | 5 | QA, notebook execution, deployment, and evidence packaging |
| Done | 6 | GitHub, public app, instructor invitation, manifest verification, data scale, and submission links |
| Blocked | 1 | Honest method gap for full routing / GTFS work |

The Sprint 5 card `Screenshot set: Trello board, public app map, and GitHub repository captured under docs/screenshots/` now includes image attachments and a visible screenshot cover on the board. Attached evidence files include the public app map, GitHub repository screenshot, and Trello board screenshots.

## Data And Method Evidence

- `data/processed/project_manifest.json` documents source provenance, collection-date notes, speed assumptions, scoring logic, Track A indicator status, external platform links, and limitations.
- `app/data/project_manifest.json` mirrors the manifest used by the deployed app.
- The latest generated payload contains `14,641` H3 r8 features and is built from a `33,021` cell 500 m grid.
- The app payload is intentionally lightweight for browser use: `app/data/shanghai_h3_seed_min.json`.

## Verification Notes

- GitHub repository returned HTTP `200`.
- GitHub Pages app returned HTTP `200`.
- Public manifest returned HTTP `200` and included:
  - `github_repository`: `https://github.com/usera3/shanghai-15mc`
  - `public_deployment_url`: `https://usera3.github.io/shanghai-15mc/`
  - `trello_shared_board`: `https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi`
  - `trello_instructor_invited`: `true`
- The latest GitHub Actions Pages deployment was successful when checked after the Trello documentation update.
