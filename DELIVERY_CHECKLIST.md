# Shanghai 15MC Delivery Checklist

## Current Local Status

- Three documented notebooks exist in `notebooks/`.
- Processed H3 app payload exists at `app/data/shanghai_h3_seed_min.json`.
- The local web app runs at `http://127.0.0.1:4173`.
- GitHub repository exists at `https://github.com/usera3/shanghai-15mc`.
- Public GitHub Pages deployment exists at `https://usera3.github.io/shanghai-15mc/`.
- Trello board exists at `https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi`.
- The instructor has been invited to the Trello board.
- The app includes mode toggles, baseline / track / composite toggles, a hex detail panel, recommender sliders, top-10 highlighting, and a data transparency panel.
- Walk and bike scores include cached road-network nearest-amenity access.
- Transit and car remain proxy surfaces, documented in `project_manifest.json`.
- AQI and Sentinel-2 NDVI proxy layers are attached to grid and H3 outputs.
- Source provenance, collection-date notes, scoring logic, Track A coverage, and limitations are recorded in `project_manifest.json`.
- AI assistance is explicitly documented in `AI_ASSISTANCE.md`.
- Static deployment notes are documented in `DEPLOYMENT_NOTES.md`.
- A Trello board template is prepared in `TRELLO_BOARD_TEMPLATE.md` and has been applied to the Trello board.
- Delivery screenshots and verification notes are documented in `docs/DELIVERY_EVIDENCE.md`.

## Required External Steps

1. Create or update a GitHub repository with this `shanghai_15mc` folder. Done: `https://github.com/usera3/shanghai-15mc`.
2. Deploy `app/` as a static site. Done: `https://usera3.github.io/shanghai-15mc/`.
3. Record the deployed URL in the submission. Done: `https://usera3.github.io/shanghai-15mc/`.
4. Create the Trello board named `15MC Shanghai - [Your Name]`. Done: `https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi`.
5. Add the instructor as a board member and share the board link. Done: instructor invited; board link recorded above.

All required external platform steps are complete.

## Trello Board Columns

- Backlog
- Sprint 1 - Week 1
- Sprint 2 - Week 2
- Sprint 3 - Week 3
- Sprint 4 - Week 4
- Sprint 5 - Week 5
- Done
- Blocked

## Suggested Trello Cards

- Review 15-minute city literature and equity critique
- Prepare local geospatial Python environment
- Decode and inspect POI 2024 archive
- Build 500 m Shanghai grid
- Process Anjuke housing price proxy
- Attach 2024 POI categories for baseline indicators
- Build walk and bike road-network access cache
- Attach AQI and Sentinel-2 NDVI layers
- Aggregate grid metrics to H3 r8
- Implement scoring weights for baseline and Track A
- Build interactive H3 web app
- Add recommender sliders and top-10 highlight
- Add data transparency and limitation panel
- Test mobile layout and app performance
- Deploy public app URL
- Final notebook review and export

## Remaining Method Gaps To Be Honest About

- Full polygonal 15-minute isochrones are not yet generated from a routing API.
- Transit does not yet use GTFS headways or timetable-aware travel time.
- Housing affordability is based on sale-price proxy data, not true rent listings.

## Local Verification Commands

```powershell
$env:PYTHONPATH=(Resolve-Path '.\pydeps')
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\build_15mc_seed.py'
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\generate_notebooks.py'
& 'C:\Users\mozi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '.\shanghai_15mc\scripts\execute_project_notebooks.py'
```
