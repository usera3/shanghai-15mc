# Trello Board Template

Board name: `15MC Shanghai - [Your Name]`

Columns:

- Backlog
- Sprint 1 - Week 1
- Sprint 2 - Week 2
- Sprint 3 - Week 3
- Sprint 4 - Week 4
- Sprint 5 - Week 5
- Done
- Blocked

Labels:

- Data
- Analysis
- App
- Literature
- Review

## Suggested Cards

Each Trello card should include acceptance criteria, a checklist, a label, and a due date inside its sprint week.

| Sprint | Label | Card title | Acceptance criteria |
|---|---|---|---|
| Sprint 1 | Literature | Review 15-minute city measurement and equity literature | Notebook 01 opens with an 800-word review and at least four cited papers. |
| Sprint 1 | Data | Prepare local geospatial Python environment | Pipeline scripts and notebooks run from a clean shell with documented commands. |
| Sprint 2 | Data | Decode and inspect POI 2024 archive | POI source inventory and mapping notes are saved under `data/processed/`. |
| Sprint 2 | Analysis | Build 500 m Shanghai grid | Grid layer is clipped to Shanghai boundary and exported before H3 aggregation. |
| Sprint 2 | Data | Process Anjuke housing price proxy | Housing samples are aggregated and missing areas are explicitly flagged. |
| Sprint 3 | Analysis | Build walk and bike road-network access cache | Cached walk/bike nearest-amenity fields are generated and joined to grid scores. |
| Sprint 3 | Analysis | Attach AQI and NDVI proxy layers | Environmental fields appear in grid, H3, app payload, and manifest documentation. |
| Sprint 3 | Analysis | Aggregate grid metrics to H3 r8 | H3 scored JSON and GeoJSON outputs are reproducible from the scripts. |
| Sprint 4 | App | Build interactive H3 web app | App includes choropleth map, mode/layer toggles, hex detail, and transparency panel. |
| Sprint 4 | App | Add where-to-live recommender | Slider weights recompute top-10 H3 recommendations and highlight them on the map. |
| Sprint 5 | Review | Test mobile layout and performance | App loads on desktop and mobile widths with no console errors in local testing. |
| Sprint 5 | Review | Final notebook review and execution | Three executed notebooks complete end-to-end and reflect current outputs. |
| Sprint 5 | App | Deploy public app URL | External step: deployed URL is recorded in the final submission. |
