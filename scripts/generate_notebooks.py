from __future__ import annotations

import os
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = ROOT / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)


LIT_REVIEW = """# 01 Data Collection

## Literature Review

The 15-minute city has become one of the most influential recent planning ideas because it shifts
attention away from mobility as speed alone and toward mobility as everyday access. Moreno et al.
(2021) frame the model as a human-centred urbanism in which essential activities should be reachable
within a short walk or bike ride. Their argument is not only environmental. It also links proximity
to resilience, public health, local identity, and the reduction of forced car dependence. For a city
like Shanghai, this matters because a metropolitan system can perform well at a macro scale while still
producing highly uneven neighbourhood-level access to daily services. In that sense, the 15-minute city
is best understood as an accessibility project rather than a simple transport project.

That distinction is important in light of the earlier accessibility literature. Geurs and van Wee
(2004) argue that accessibility should be evaluated through multiple interacting components: land use,
transport, time, and the characteristics of individuals. Their review remains useful because it warns
against reducing accessibility to distance or travel time alone. A neighbourhood may be close to many
destinations, but the quality, affordability, or suitability of those destinations also matters.
Likewise, the same spatial structure can be experienced very differently by walkers, cyclists, transit
users, older adults, or lower-income households. This project follows that logic by combining service
density, transport structure, housing cost proxies, and track-specific amenities instead of relying on
a single nearest-destination measure.

The equity dimension is equally central. Lucas (2012) shows that transport disadvantage and social
exclusion are deeply connected, particularly when essential opportunities are spatially available only
to households that can afford the time, money, or mode required to reach them. This critique matters
for 15-minute city work because proximity can easily become a premium urban good. If high-access areas
are systematically more expensive, then a city may score well on livability while still excluding many
residents from those advantages. For Shanghai, where land values and neighbourhood status vary sharply
across the inner city, new towns, and peripheral districts, a 15-minute analysis should therefore ask
not only where amenities cluster, but also who can realistically benefit from them.

Pozoukidou and Chatziyiannaki (2021) extend this discussion by treating the 15-minute city as both a
planning model and a political imagination. They argue that proximity-based planning cannot be reduced
to a decorative slogan about compactness; it must be operationalised through measurable indicators of
walkability, mixed functions, and neighbourhood regeneration. At the same time, they warn that the
model can become utopian if planners ignore institutional capacity, spatial inequality, and the uneven
quality of the urban fabric. This is a useful warning for a Shanghai workflow because it suggests that
an analytical pipeline should stay explicit about its assumptions, scales, and blind spots. A map of
"good" 15-minute areas is only meaningful if the scoring logic is transparent and the missing data are
clearly documented.

The prototype developed in this project therefore adopts three principles from the literature. First,
it treats accessibility as a multi-dimensional condition rather than a single travel metric. Second, it
keeps equity visible by pairing amenity access with a housing-cost proxy. Third, it builds the analysis
so that methods can be upgraded in stages: starting from cell-level and H3 proxy indicators, then moving
toward fully network-based isochrones and richer real-time data once the pipeline is stable. This staged
strategy is especially appropriate for a five-week intensive project, where reproducibility and design
clarity matter as much as model sophistication.

In practical terms, the literature supports a workflow that begins with raw spatial datasets, validates
their provenance, constructs a common spatial framework, and only then derives scores. That order is not
administrative busywork. It is what makes later interpretation credible. If the 15-minute city is about
everyday life, then the analysis must remain anchored in documented sources, defensible category choices,
and readable visual outputs. The notebooks in this prototype are structured around that logic: notebook
01 documents sources and cleaning, notebook 02 defines the grid and accessibility logic, and notebook 03
makes the scoring and H3 aggregation fully inspectable. The result is not yet a finished urban policy
instrument, but it is a reproducible analytical foundation for one.

### References

1. Moreno, C., Allam, Z., Chabaud, D., Gall, C., & Pratlong, F. (2021). *Introducing the “15-Minute City”:
   Sustainability, Resilience and Place Identity in Future Post-Pandemic Cities*. Smart Cities, 4(1), 93-111.
2. Geurs, K. T., & van Wee, B. (2004). *Accessibility evaluation of land-use and transport strategies:
   review and research directions*. Journal of Transport Geography, 12(2), 127-140.
3. Lucas, K. (2012). *Transport and social exclusion: Where are we now?* Transport Policy, 20, 105-113.
4. Pozoukidou, G., & Chatziyiannaki, Z. (2021). *15-Minute City: Decomposing the New Urban Planning Eutopia*.
   Sustainability, 13(2), 928.
"""


def markdown_cell(text: str):
    return nbf.v4.new_markdown_cell(text)


def code_cell(text: str):
    return nbf.v4.new_code_cell(text)


def notebook_01():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        markdown_cell(LIT_REVIEW),
        markdown_cell(
            """## Project Data Inventory

This notebook documents the raw and processed inputs currently used by the prototype:

- `UTSEUS-anjuke-real-estate.csv`
- `POI 2024.zip`
- extracted classified 2024 POI CSVs under `data/raw/poi_2024/POI 2024/csv格式/已分类`
- `shanghai-roads-simplified.parquet`
- Shanghai municipal boundary from Aliyun DataV

The current prototype uses the 2024 classified POI extracts as its main amenity layer.
Type-based filtering notes are stored in `poi_2024_probe.json` and `poi_2024_mapping_notes.md`.
It also produces a `500 m` grid-level processed layer before aggregation to H3.
"""
        ),
        markdown_cell(
            """## Source Provenance Log

The project brief requires at least four distinct datasets and explicit provenance logging. The current
prototype uses five source groups: housing, POI amenities, road network, municipal boundary, and
environmental proxies. The manifest below stores the public-facing provenance log without exposing
machine-specific absolute paths.
"""
        ),
        code_cell(
            """from pathlib import Path
import json
import os
import pandas as pd

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
RAW_DIR = Path(os.environ.get("SHANGHAI_15MC_RAW_DIR", ROOT / "data" / "raw"))
APARTMENT_PATH = Path(os.environ.get("SHANGHAI_15MC_APARTMENT_PATH", ROOT / "data" / "raw" / "anjuke_price_distance_filtered.parquet"))
if not APARTMENT_PATH.exists():
    APARTMENT_PATH = ROOT.parent / "anjuke_price_distance_filtered.parquet"
ROADS_PATH = Path(os.environ.get("SHANGHAI_15MC_ROADS_PATH", ROOT / "data" / "raw" / "shanghai-roads-simplified.parquet"))
PROCESSED = ROOT / "data" / "processed"

inventory = [
    RAW_DIR / "UTSEUS-anjuke-real-estate.csv",
    RAW_DIR / "POI 2024.zip",
    APARTMENT_PATH,
    ROADS_PATH,
    ROOT / "data" / "raw" / "poi_2024" / "POI 2024" / "csv格式" / "已分类",
    PROCESSED / "project_manifest.json",
    PROCESSED / "poi_2024_probe.json",
    PROCESSED / "shanghai_grid_seed.json",
]

pd.DataFrame(
    [
        {"file": str(p), "exists": p.exists(), "size_mb": round(p.stat().st_size / 1_048_576, 2) if p.exists() else None}
        for p in inventory
    ]
)"""
        ),
        markdown_cell("## Processed Prototype Manifest"),
        code_cell(
            """manifest = json.loads((PROCESSED / "project_manifest.json").read_text(encoding="utf-8"))
manifest"""
        ),
        code_cell(
            """pd.DataFrame(manifest["source_provenance"])[[
    "id",
    "source",
    "type",
    "role",
    "collection_date",
    "processing_note",
]]"""
        ),
        markdown_cell("## Apartment Data Preview"),
        code_cell(
            """apartment = pd.read_parquet(APARTMENT_PATH)
apartment[["longitude", "latitude", "onesquaremeter", "distances"]].describe().T"""
        ),
        markdown_cell("## Road Network Preview"),
        code_cell(
            """roads = pd.read_parquet(ROADS_PATH)
roads.head()"""
        ),
        markdown_cell(
            """## AI Assistance And Integrity Note

AI assistance was used for code scaffolding, debugging, documentation drafting, local QA, and app
iteration. The final responsibility for source compliance, interpretation, weighting choices, and
submission decisions remains with the student. See `AI_ASSISTANCE.md` in the project root.
"""
        ),
        markdown_cell(
            """## Final Source-Review Notes

The current local prototype already logs source provenance in `project_manifest.json`. Before public
submission, review source terms and append any final API-based collection details, especially if the
proxy workflow is upgraded with routing or GTFS data:

1. how the 2024 POI archive was decoded and refreshed
2. any API usage for routing or GTFS retrieval
3. data collection dates for each layer
4. licensing / terms-of-service checks
5. a reproducible source log for all derived files

The static project files do not include API keys or private credentials.
"""
        ),
    ]
    return nb


def notebook_02():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        markdown_cell(
            """# 02 Grid And Isochrones

This notebook sets up the spatial framework for the 15-minute analysis.

The current prototype builds the spatial logic in two layers:

1. a **500 m projected grid** for neighbourhood-scale computation
2. an **H3 r8 aggregation** for visualization and public communication

In the fully finished version of the project, this notebook should compute true 15-minute walk,
bike, transit, and car isochrones from each grid centroid. In the current local prototype, the grid
already exists and receives four-mode **15-minute radius proxy accessibility scores** before being
aggregated to H3. Walk and bike are further improved with road-network nearest-amenity accessibility
using the simplified Shanghai road graph. Transit and car remain proxy surfaces until GTFS or a routing
API is available.
"""
        ),
        code_cell(
            """from pathlib import Path
from urllib.request import urlopen
import json
import numpy as np
import pandas as pd
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union, transform
from pyproj import Transformer

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
BOUNDARY_URL = "https://geo.datav.aliyun.com/areas_v3/bound/310000.json"
BOUNDARY_CACHE = ROOT / "data" / "raw" / "shanghai_boundary_310000.json"

if BOUNDARY_CACHE.exists():
    geojson = json.loads(BOUNDARY_CACHE.read_text(encoding="utf-8"))
else:
    with urlopen(BOUNDARY_URL) as resp:
        geojson = json.load(resp)
boundary = unary_union([shape(feature["geometry"]) for feature in geojson["features"]])

to_4576 = Transformer.from_crs(4326, 4576, always_xy=True).transform
to_4326 = Transformer.from_crs(4576, 4326, always_xy=True).transform
boundary_4576 = transform(to_4576, boundary)
boundary_4576.area / 1_000_000"""
        ),
        markdown_cell("## Build A 500 m Grid"),
        code_cell(
            """minx, miny, maxx, maxy = boundary_4576.bounds
cell = 500
cells = []

for x0 in np.arange(minx, maxx, cell):
    for y0 in np.arange(miny, maxy, cell):
        sq = box(x0, y0, x0 + cell, y0 + cell)
        if sq.intersects(boundary_4576):
            cells.append(sq)

len(cells)"""
        ),
        markdown_cell(
            """The count above should land in the same order of magnitude as the brief expectation of roughly
25,000 cells, depending on the exact boundary geometry and edge treatment.
"""
        ),
        code_cell(
            """centroids = [sq.centroid for sq in cells]
lonlat = [Transformer.from_crs(4576, 4326, always_xy=True).transform(pt.x, pt.y) for pt in centroids]
grid_preview = pd.DataFrame(lonlat, columns=["longitude", "latitude"])
grid_preview.head()"""
        ),
        markdown_cell("## Current Proxy Route"),
        code_cell(
            """manifest = json.loads((ROOT / "data" / "processed" / "project_manifest.json").read_text(encoding="utf-8"))
manifest["limitations"]"""
        ),
        markdown_cell("## Current Method Summary"),
        code_cell(
            """pd.DataFrame({"step": manifest["method_summary"]})"""
        ),
        markdown_cell("## Mode Speed Assumptions"),
        code_cell(
            """pd.Series(manifest["speed_assumptions_m_s"], name="meters_per_second").to_frame()"""
        ),
        markdown_cell("## Current Processed Grid Layer"),
        code_cell(
            """grid_seed = pd.read_json(ROOT / "data" / "processed" / "shanghai_grid_seed.json")
grid_seed[[
    "grid_id",
    "center_lon",
    "center_lat",
    "proxy_access_walk",
    "proxy_access_bike",
    "proxy_access_transit",
    "proxy_access_car",
]].head()"""
        ),
        markdown_cell(
            """The current proxy interprets a 15-minute reach area as a mode-specific radius over the 500 m grid:

- walk: `1.33 m/s`
- bike: `3.05 m/s`
- transit: `4.5 m/s`
- car: `8.3 m/s`

This is still a simplification, but it is closer to the assignment logic than a plain nearest-neighbour or
hex-ring average.
"""
        ),
        markdown_cell("## Walk / Bike Road-Network Accessibility Cache"),
        code_cell(
            """network_cache = pd.read_json(ROOT / "data" / "processed" / "shanghai_network_accessibility_grid.json")
network_cache[[
    "grid_id",
    "network_access_walk",
    "network_access_bike",
    "network_track_access_walk",
    "network_track_access_bike",
]].describe().T"""
        ),
        markdown_cell(
            """## Upgrade Path To Full Isochrones

To turn this into the final notebook required by the course:

1. snap each 500 m centroid to the walk, bike, transit, and car networks
2. generate 15-minute reach polygons or reachable edge sets
3. cache network queries by mode
4. join POIs and environmental layers against each isochrone
5. export cell-level scores for notebook 03
"""
        ),
    ]
    return nb


def notebook_03():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        markdown_cell(
            """# 03 Scoring And H3

This notebook documents the current H3 aggregation and scoring logic for the prototype.

The implemented local baseline uses:

- housing sale-price proxy from Anjuke
- nearest subway distance from the regression preprocessing step
- a `has_housing_sample` flag so missing housing data are not treated as cheap housing
- 2024 POI-based counts for schools, healthcare, groceries, convenience stores, parks, bus stops, and subway access
- bike / walk road availability proxies from the simplified Shanghai road network
- a 500 m processed grid layer as the intermediate scale before H3 aggregation
- mode-specific 15-minute radius proxy accessibility fields computed on the grid
- cached walk / bike road-network nearest-amenity access fields
- environmental layers from public APIs and remote sensing (`AQI` and Sentinel-2 `NDVI` are attached)

The current selected track is:

- **Track A — Healthy Lifestyle & Sport**
"""
        ),
        code_cell(
            """from pathlib import Path
import json
import pandas as pd

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
seed = json.loads((ROOT / "data" / "processed" / "shanghai_h3_seed.json").read_text(encoding="utf-8"))
df = pd.DataFrame(seed)
df.head()"""
        ),
        markdown_cell("## Grid Layer Preview"),
        code_cell(
            """grid_df = pd.read_json(ROOT / "data" / "processed" / "shanghai_grid_seed.json")
grid_df[[
    "grid_id",
    "proxy_access_walk",
    "proxy_access_bike",
    "proxy_access_transit",
    "proxy_access_car",
    "h3",
]].head()"""
        ),
        markdown_cell("## Key Score Fields"),
        code_cell(
            """score_cols = [c for c in df.columns if c.startswith("score_")]
score_cols"""
        ),
        markdown_cell("## Scoring Rationale"),
        code_cell(
            """manifest = json.loads((ROOT / "data" / "processed" / "project_manifest.json").read_text(encoding="utf-8"))
pd.Series(manifest["score_method"], name="description").to_frame()"""
        ),
        markdown_cell("## Track A Indicator Coverage"),
        code_cell(
            """pd.Series(manifest["track_indicator_status"], name="status").to_frame()"""
        ),
        code_cell(
            """df[
    [
        "score_baseline_walk",
        "score_track_walk",
        "score_composite_walk",
        "network_access_walk",
        "network_track_access_walk",
        "has_housing_sample",
        "avg_price_m2",
        "avg_subway_distance_m",
        "top_amenities",
    ]
].sort_values("score_composite_walk", ascending=False).head(15)"""
        ),
        markdown_cell("## Composite Score Distribution"),
        code_cell(
            """df[["score_composite_walk", "score_composite_bike", "score_composite_transit", "score_composite_car"]].describe().T"""
        ),
        markdown_cell("## Suggested Interpretation"),
        markdown_cell(
            """The current prototype should be interpreted as a **screening surface** rather than a final
decision map. High-scoring hexes indicate where multiple supportive amenities, transit access, and
healthy-lifestyle signals overlap. Walk and bike now include local road-network access to key
amenities, while transit and car still rely on proxy surfaces instead of full timetable-aware or
routing-engine isochrones.
"""
        ),
        markdown_cell("## Final-Step Upgrade Checklist"),
        markdown_cell(
            """1. Replace POI density proxies with counts inside real 15-minute mode isochrones.
2. Replace stop-density transit proxies with GTFS-aware service coverage.
3. Replace sale-price proxy with true rent / affordability layers if Track C is chosen.
4. Deploy the public web app and record the final URL.
5. Document the weighting rationale with sensitivity tests.
"""
        ),
    ]
    return nb


def main() -> None:
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    notebooks = {
        "01_data_collection.ipynb": notebook_01(),
        "02_grid_isochrones.ipynb": notebook_02(),
        "03_scoring_h3.ipynb": notebook_03(),
    }
    for name, nb in notebooks.items():
        nbf.write(nb, NOTEBOOKS_DIR / name)
    print("Created:", ", ".join(notebooks.keys()))


if __name__ == "__main__":
    main()
