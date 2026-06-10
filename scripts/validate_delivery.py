"""Validate the Shanghai 15MC delivery package.

The checks are intentionally evidence-oriented: they verify that the app data,
manifest, notebooks, screenshots, disclosures, and optional public URLs line up
with the submission claims rather than only checking that files exist.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_APP_FILES = [
    "app/index.html",
    "app/styles.css",
    "app/app.js",
    "app/data/shanghai_h3_seed_min.json",
    "app/data/project_manifest.json",
]

EXPECTED_NOTEBOOKS = {
    "notebooks/01_data_collection.ipynb": [
        "# 01 Data Collection",
        "Source Provenance",
        "Project Data Inventory",
    ],
    "notebooks/02_grid_isochrones.ipynb": [
        "# 02 Grid And Isochrones",
        "500 m",
        "Speed Assumptions",
    ],
    "notebooks/03_scoring_h3.ipynb": [
        "# 03 Scoring And H3",
        "Scoring Rationale",
        "Track A Indicator",
    ],
}

EXPECTED_SCREENSHOTS = [
    "docs/screenshots/github-repository.png",
    "docs/screenshots/public-app-map.png",
    "docs/screenshots/trello-board-backlog-sprint1.png",
    "docs/screenshots/trello-board-sprints-done-blocked.png",
    "docs/screenshots/trello-board-all-lists-empty-before-card-fill.png",
    "docs/screenshots/trello-card-image-attachments-visible.png",
    "docs/screenshots/trello-board-card-cover-visible.png",
    "docs/screenshots/trello-board-weekly-tasks-detailed.png",
]

EXPECTED_SCHEMA_FIELDS = [
    "h3_index",
    "top_amenities",
    "housing_band",
    "has_housing_sample",
    "avg_price_m2",
    "avg_subway_distance_m",
    "ndvi",
    "ndvi_norm",
    "european_aqi",
    "aqi_norm",
    "school_count",
    "healthcare_count",
    "grocery_count",
    "park_count",
    "bus_stop_count",
    "subway_exit_count",
    "gym_count",
    "bike_length_km",
    "price_affordability_norm",
    "transit_norm",
    "park_norm",
    "score_baseline_walk",
    "score_baseline_bike",
    "score_baseline_transit",
    "score_baseline_car",
    "score_track_walk",
    "score_track_bike",
    "score_track_transit",
    "score_track_car",
    "score_composite_walk",
    "score_composite_bike",
    "score_composite_transit",
    "score_composite_car",
    "proxy_access_walk",
    "proxy_access_bike",
    "proxy_access_transit",
    "proxy_access_car",
    "network_access_walk",
    "network_access_bike",
    "network_track_access_walk",
    "network_track_access_bike",
    "grid_cell_count",
]

SCORE_FIELDS = [
    f"score_{layer}_{mode}"
    for layer in ("baseline", "track", "composite")
    for mode in ("walk", "bike", "transit", "car")
]

PROXY_ACCESS_FIELDS = [f"proxy_access_{mode}" for mode in ("walk", "bike", "transit", "car")]

NETWORK_ACCESS_FIELDS = [
    "network_access_walk",
    "network_access_bike",
    "network_track_access_walk",
    "network_track_access_bike",
]

MANIFEST_REQUIRED_KEYS = [
    "project",
    "track",
    "description",
    "created_at_utc",
    "h3_resolution",
    "grid_cell_size_m",
    "grid_cell_count",
    "feature_count",
    "source_files",
    "source_provenance",
    "method_summary",
    "speed_assumptions_m_s",
    "score_method",
    "track_indicator_status",
    "external_platform_status",
    "limitations",
    "mode_score_fields",
    "ranges",
]


@dataclass
class Check:
    status: str
    name: str
    detail: str


class Report:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def pass_(self, name: str, detail: str) -> None:
        self.checks.append(Check("PASS", name, detail))

    def warn(self, name: str, detail: str) -> None:
        self.checks.append(Check("WARN", name, detail))

    def fail(self, name: str, detail: str) -> None:
        self.checks.append(Check("FAIL", name, detail))

    def has_failures(self) -> bool:
        return any(check.status == "FAIL" for check in self.checks)

    def has_warnings(self) -> bool:
        return any(check.status == "WARN" for check in self.checks)

    def print(self) -> None:
        width = max(len(check.name) for check in self.checks) if self.checks else 0
        for check in self.checks:
            print(f"[{check.status}] {check.name:<{width}}  {check.detail}")

        counts = {status: sum(1 for check in self.checks if check.status == status) for status in ("PASS", "WARN", "FAIL")}
        print()
        print(f"Summary: {counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failures.")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def values_for_field(features: list[Any], field_index: int) -> list[Any]:
    values: list[Any] = []
    for feature in features:
        if not isinstance(feature, list) or len(feature) != 2:
            continue
        row = feature[1]
        if isinstance(row, list) and field_index < len(row):
            values.append(row[field_index])
    return values


def require_files(report: Report, root: Path, paths: Iterable[str], name: str) -> None:
    missing = [path for path in paths if not (root / path).is_file()]
    if missing:
        report.fail(name, "Missing: " + ", ".join(missing))
        return
    report.pass_(name, f"{len(list(paths))} expected files are present.")


def check_static_app(report: Report, root: Path) -> None:
    require_files(report, root, EXPECTED_APP_FILES, "Static app files")

    index_path = root / "app/index.html"
    app_js_path = root / "app/app.js"
    styles_path = root / "app/styles.css"
    if not (index_path.is_file() and app_js_path.is_file() and styles_path.is_file()):
        return

    index = read_text(index_path)
    app_js = read_text(app_js_path)
    styles = read_text(styles_path)

    index_terms = [
        "leaflet-map",
        "hex-map",
        "mode-toggle",
        "layer-toggle",
        "overlay-opacity",
        "recommendations-content",
        "manifest-content",
        "OpenStreetMap",
    ]
    missing_index_terms = [term for term in index_terms if term not in index]
    if missing_index_terms:
        report.fail("App HTML controls", "Missing expected UI hooks: " + ", ".join(missing_index_terms))
    else:
        report.pass_("App HTML controls", "Map, mode/layer toggles, opacity control, recommendations, and transparency hooks are present.")

    app_terms = [
        "L.map",
        "tile.openstreetmap.org",
        "shanghai_h3_seed_min.json",
        "project_manifest.json",
        "score_",
        "overlayOpacity",
        "computeRecommendation",
        "bindRecommendationButtons",
    ]
    missing_app_terms = [term for term in app_terms if term not in app_js]
    if missing_app_terms:
        report.fail("App JS behavior", "Missing expected behavior markers: " + ", ".join(missing_app_terms))
    else:
        report.pass_("App JS behavior", "Leaflet basemap, payload loading, score switching, opacity, and recommendations are wired.")

    if "@media" in styles and "#hex-map" in styles and "#map" in styles:
        report.pass_("App CSS", "Responsive styling and map/canvas styles are present.")
    else:
        report.warn("App CSS", "Could not confirm responsive map styling markers in styles.css.")


def check_payload(report: Report, root: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    payload_path = root / "app/data/shanghai_h3_seed_min.json"
    manifest_path = root / "app/data/project_manifest.json"
    if not payload_path.is_file() or not manifest_path.is_file():
        report.fail("App data", "App payload or manifest is missing.")
        return None, None

    try:
        payload = load_json(payload_path)
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as exc:
        report.fail("App data JSON", f"JSON parsing failed: {exc}")
        return None, None

    schema = payload.get("schema")
    features = payload.get("features")
    if not isinstance(schema, list) or not isinstance(features, list):
        report.fail("Payload shape", "Expected top-level schema list and features list.")
        return payload, manifest

    missing_fields = [field for field in EXPECTED_SCHEMA_FIELDS if field not in schema]
    if missing_fields:
        report.fail("Payload schema", "Missing fields: " + ", ".join(missing_fields))
    else:
        report.pass_("Payload schema", f"All {len(EXPECTED_SCHEMA_FIELDS)} expected H3/app fields are present.")

    expected_count = manifest.get("feature_count")
    if expected_count == len(features) and len(features) >= 10_000:
        report.pass_("H3 feature count", f"{len(features):,} features match manifest and exceed the delivery scale threshold.")
    else:
        report.fail("H3 feature count", f"Payload has {len(features):,}; manifest feature_count is {expected_count!r}.")

    if len(schema) != len(set(schema)):
        report.fail("Schema uniqueness", "Duplicate schema field names detected.")
    else:
        report.pass_("Schema uniqueness", "Schema field names are unique.")

    row_length_errors = 0
    geometry_errors = 0
    h3_values: list[str] = []
    h3_field = schema.index("h3_index") if "h3_index" in schema else -1
    for feature in features:
        if not isinstance(feature, list) or len(feature) != 2:
            row_length_errors += 1
            continue
        geometry, row = feature
        if not isinstance(row, list) or len(row) != len(schema):
            row_length_errors += 1
        if not isinstance(geometry, list) or len(geometry) < 5:
            geometry_errors += 1
        elif any(not isinstance(point, list) or len(point) != 2 for point in geometry[:5]):
            geometry_errors += 1
        if h3_field >= 0 and isinstance(row, list) and h3_field < len(row):
            h3_values.append(str(row[h3_field]))

    if row_length_errors:
        report.fail("Payload rows", f"{row_length_errors:,} feature rows do not match [geometry, values] schema length.")
    else:
        report.pass_("Payload rows", "Every feature row has geometry plus values matching the schema length.")

    if geometry_errors:
        report.fail("Payload geometry", f"{geometry_errors:,} feature geometries are malformed.")
    else:
        report.pass_("Payload geometry", "All checked H3 polygons have coordinate pairs and at least five vertices.")

    invalid_h3 = [value for value in h3_values[:1000] if not re.match(r"^8[0-9a-f]{14}$", value)]
    if len(h3_values) == len(features) and len(set(h3_values)) == len(features) and not invalid_h3:
        report.pass_("H3 identifiers", "All H3 IDs are present, unique, and match the expected r8-like format.")
    else:
        report.fail("H3 identifiers", "H3 IDs are missing, duplicated, or not in the expected format.")

    field_index = {field: idx for idx, field in enumerate(schema)}
    for group_name, fields in (
        ("Score fields", SCORE_FIELDS),
        ("Proxy access fields", PROXY_ACCESS_FIELDS),
        ("Network access fields", NETWORK_ACCESS_FIELDS),
    ):
        missing = [field for field in fields if field not in field_index]
        if missing:
            report.fail(group_name, "Missing fields: " + ", ".join(missing))
            continue
        bad_fields = []
        zero_only_fields = []
        for field in fields:
            values = values_for_field(features, field_index[field])
            numeric_values = [float(value) for value in values if is_number(value)]
            if len(numeric_values) != len(features):
                bad_fields.append(field)
                continue
            if min(numeric_values) < -0.0001 or max(numeric_values) > 100.0001:
                bad_fields.append(field)
            if max(numeric_values) <= 0:
                zero_only_fields.append(field)
        if bad_fields:
            report.fail(group_name, "Non-numeric or out-of-range 0-100 values: " + ", ".join(bad_fields))
        elif zero_only_fields:
            report.fail(group_name, "Fields contain only zero values: " + ", ".join(zero_only_fields))
        else:
            report.pass_(group_name, f"{len(fields)} fields are numeric, populated, and within the 0-100 score range.")

    environment_checks = {
        "ndvi": (-1.0, 1.0),
        "ndvi_norm": (0.0, 1.0),
        "european_aqi": (0.0, 500.0),
        "aqi_norm": (0.0, 1.0),
    }
    environment_errors = []
    for field, (low, high) in environment_checks.items():
        if field not in field_index:
            environment_errors.append(field)
            continue
        values = values_for_field(features, field_index[field])
        numeric_values = [float(value) for value in values if is_number(value)]
        if len(numeric_values) != len(features) or min(numeric_values) < low or max(numeric_values) > high:
            environment_errors.append(field)
    if environment_errors:
        report.fail("Environment fields", "Missing or out-of-range fields: " + ", ".join(environment_errors))
    else:
        report.pass_("Environment fields", "NDVI and AQI fields are populated within expected ranges.")

    return payload, manifest


def check_manifest(report: Report, root: Path, payload: dict[str, Any] | None, app_manifest: dict[str, Any] | None) -> None:
    processed_path = root / "data/processed/project_manifest.json"
    app_manifest_path = root / "app/data/project_manifest.json"
    if not processed_path.is_file() or not app_manifest_path.is_file():
        report.fail("Manifest files", "Both app/data and data/processed manifests are required.")
        return

    try:
        processed_manifest = load_json(processed_path)
        manifest = app_manifest or load_json(app_manifest_path)
    except json.JSONDecodeError as exc:
        report.fail("Manifest JSON", f"JSON parsing failed: {exc}")
        return

    if manifest == processed_manifest:
        report.pass_("Manifest mirror", "App manifest matches data/processed manifest exactly.")
    else:
        report.warn("Manifest mirror", "App manifest differs from data/processed/project_manifest.json.")

    missing_keys = [key for key in MANIFEST_REQUIRED_KEYS if key not in manifest]
    if missing_keys:
        report.fail("Manifest keys", "Missing keys: " + ", ".join(missing_keys))
    else:
        report.pass_("Manifest keys", "Required provenance, method, scoring, platform, and limitation keys are present.")

    if manifest.get("h3_resolution") == 8 and manifest.get("grid_cell_size_m") == 500:
        report.pass_("Grid settings", "Manifest records H3 r8 and 500 m grid settings.")
    else:
        report.fail("Grid settings", "Manifest should record h3_resolution=8 and grid_cell_size_m=500.")

    if payload and isinstance(payload.get("features"), list):
        if manifest.get("feature_count") == len(payload["features"]) and manifest.get("grid_cell_count", 0) >= 30_000:
            report.pass_("Manifest counts", "Feature count matches payload and grid count is at the expected Shanghai scale.")
        else:
            report.fail("Manifest counts", "Feature/grid counts do not match payload expectations.")

    source_provenance = manifest.get("source_provenance")
    if isinstance(source_provenance, list) and len(source_provenance) >= 5:
        incomplete = []
        for item in source_provenance:
            if not isinstance(item, dict) or not {"id", "source", "type", "role", "collection_date", "processing_note"}.issubset(item):
                incomplete.append(str(item.get("id", "<unknown>")) if isinstance(item, dict) else "<not-a-dict>")
        if incomplete:
            report.fail("Source provenance", "Incomplete provenance entries: " + ", ".join(incomplete))
        else:
            report.pass_("Source provenance", f"{len(source_provenance)} source provenance entries include role, collection date, and processing notes.")
    else:
        report.fail("Source provenance", "Expected at least five documented source provenance entries.")

    expected_method_terms = ["500 m", "POI", "15-minute", "network", "H3"]
    method_text = " ".join(manifest.get("method_summary", [])) if isinstance(manifest.get("method_summary"), list) else ""
    missing_terms = [term for term in expected_method_terms if term.lower() not in method_text.lower()]
    if missing_terms:
        report.warn("Method summary", "Missing expected method terms: " + ", ".join(missing_terms))
    else:
        report.pass_("Method summary", "Manifest summarizes grid, POI, accessibility, network, and H3 aggregation steps.")

    score_method = manifest.get("score_method", {})
    required_score_keys = {"normalization", "baseline", "track", "composite", "housing_missingness"}
    if isinstance(score_method, dict) and required_score_keys.issubset(score_method):
        report.pass_("Score method", "Normalization, baseline, Track A, composite, and housing-missingness logic are documented.")
    else:
        report.fail("Score method", "Score method is missing required explanation keys.")

    track_status = manifest.get("track_indicator_status", {})
    if isinstance(track_status, dict) and {"ndvi", "aqi", "fresh_market_health_food"}.issubset(track_status) and len(track_status) >= 8:
        report.pass_("Track indicators", f"{len(track_status)} Track A indicator statuses are documented.")
    else:
        report.fail("Track indicators", "Track A indicator coverage is incomplete.")

    limitations = manifest.get("limitations", [])
    limitation_text = " ".join(limitations).lower() if isinstance(limitations, list) else ""
    if all(term in limitation_text for term in ("isochrone", "gtfs", "sale-price")):
        report.pass_("Limitations", "Key proxy, GTFS/transit, and housing-sale-price limitations are disclosed.")
    else:
        report.fail("Limitations", "Expected limitations for isochrones, GTFS/transit, and sale-price proxy.")

    external = manifest.get("external_platform_status", {})
    external_requirements = {
        "github_repository": "https://github.com/",
        "public_deployment_url": "https://",
        "trello_shared_board": "https://trello.com/",
    }
    external_errors = []
    for key, prefix in external_requirements.items():
        value = external.get(key) if isinstance(external, dict) else None
        if not isinstance(value, str) or not value.startswith(prefix):
            external_errors.append(key)
    if not isinstance(external, dict) or external.get("trello_instructor_invited") is not True:
        external_errors.append("trello_instructor_invited")
    if external_errors:
        report.fail("External platform fields", "Missing or invalid: " + ", ".join(external_errors))
    else:
        report.pass_("External platform fields", "GitHub, public app, Trello link, and instructor invitation flag are recorded.")

    if payload and isinstance(payload.get("schema"), list):
        schema = set(payload["schema"])
        mode_score_fields = manifest.get("mode_score_fields", {})
        missing_references: list[str] = []
        if isinstance(mode_score_fields, dict):
            for fields in mode_score_fields.values():
                if isinstance(fields, list):
                    missing_references.extend(field for field in fields if field not in schema)
        if missing_references:
            report.fail("Manifest field refs", "Manifest references fields absent from payload schema: " + ", ".join(sorted(set(missing_references))))
        else:
            report.pass_("Manifest field refs", "All manifest mode/environment field references exist in the app payload schema.")


def check_notebooks(report: Report, root: Path) -> None:
    missing = [path for path in EXPECTED_NOTEBOOKS if not (root / path).is_file()]
    if missing:
        report.fail("Notebook files", "Missing: " + ", ".join(missing))
        return
    report.pass_("Notebook files", f"{len(EXPECTED_NOTEBOOKS)} required notebooks are present.")

    for notebook_path, expected_terms in EXPECTED_NOTEBOOKS.items():
        path = root / notebook_path
        try:
            notebook = load_json(path)
        except json.JSONDecodeError as exc:
            report.fail(f"Notebook structure {path.name}", f"JSON parsing failed: {exc}")
            continue

        cells = notebook.get("cells", [])
        markdown_cells = [cell for cell in cells if cell.get("cell_type") == "markdown"]
        code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
        source_text = "\n".join("".join(cell.get("source", [])) for cell in cells)
        missing_terms = [term for term in expected_terms if term not in source_text]
        if len(markdown_cells) >= 5 and len(code_cells) >= 4 and not missing_terms:
            report.pass_(f"Notebook structure {path.name}", f"{len(markdown_cells)} markdown cells and {len(code_cells)} code cells cover the expected topics.")
        else:
            report.fail(
                f"Notebook structure {path.name}",
                f"Expected documented markdown/code cells and topic terms; missing terms: {', '.join(missing_terms) or 'none'}.",
            )

        executed_copy = path.with_name(path.stem + ".executed.ipynb")
        executed_notebook = notebook
        executed_source = "base notebook"
        if executed_copy.is_file():
            try:
                executed_notebook = load_json(executed_copy)
                executed_source = executed_copy.name
            except json.JSONDecodeError:
                executed_notebook = notebook
                executed_source = "base notebook"
        executed_code = [cell for cell in executed_notebook.get("cells", []) if cell.get("cell_type") == "code"]
        executed_cells = [
            cell
            for cell in executed_code
            if cell.get("execution_count") is not None or cell.get("outputs")
        ]
        if executed_code and len(executed_cells) == len(executed_code):
            report.pass_(f"Notebook execution {path.name}", f"All {len(executed_code)} code cells have execution evidence in {executed_source}.")
        else:
            report.warn(
                f"Notebook execution {path.name}",
                "Base notebook has no full execution evidence and no complete .executed.ipynb sibling was found.",
            )


def check_documents_and_evidence(report: Report, root: Path) -> None:
    docs = [
        "README.md",
        "SUBMISSION_SUMMARY.md",
        "DELIVERY_CHECKLIST.md",
        "DEPLOYMENT_NOTES.md",
        "AI_ASSISTANCE.md",
        "TRELLO_BOARD_TEMPLATE.md",
        "docs/DELIVERY_EVIDENCE.md",
    ]
    require_files(report, root, docs, "Delivery documents")

    if not all((root / path).is_file() for path in docs):
        return

    readme = read_text(root / "README.md")
    summary = read_text(root / "SUBMISSION_SUMMARY.md")
    checklist = read_text(root / "DELIVERY_CHECKLIST.md")
    deploy = read_text(root / "DEPLOYMENT_NOTES.md")
    ai_disclosure = read_text(root / "AI_ASSISTANCE.md")
    evidence = read_text(root / "docs/DELIVERY_EVIDENCE.md")

    shared_text = "\n".join([readme, summary, checklist, evidence])
    required_links = [
        "https://github.com/usera3/shanghai-15mc",
        "https://usera3.github.io/shanghai-15mc/",
        "https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi",
    ]
    missing_links = [link for link in required_links if link not in shared_text]
    if missing_links:
        report.fail("Documented links", "Missing links: " + ", ".join(missing_links))
    else:
        report.pass_("Documented links", "GitHub, public app, and Trello links are recorded in delivery docs.")

    summary_terms = [
        "Requirement Evidence Map",
        "Public interactive web app",
        "500 m grid workflow",
        "H3 aggregation",
        "AI assistance disclosure",
        "scripts/validate_delivery.py",
    ]
    missing_summary_terms = [term for term in summary_terms if term not in summary]
    if missing_summary_terms:
        report.fail("Submission summary", "Missing marker-facing terms: " + ", ".join(missing_summary_terms))
    else:
        report.pass_("Submission summary", "Marker-facing requirement-to-evidence map is documented.")

    if "AI Assistance" in ai_disclosure and "Human Review Needed" in ai_disclosure and "No API keys" in ai_disclosure:
        report.pass_("AI disclosure", "AI assistance scope, human review, and credential note are disclosed.")
    else:
        report.fail("AI disclosure", "AI_ASSISTANCE.md is missing expected disclosure language.")

    deploy_lower = deploy.lower()
    if "app/" in deploy and "static" in deploy_lower and "build" in deploy_lower:
        report.pass_("Deployment notes", "Static app publish directory and no-build deployment guidance are documented.")
    else:
        report.fail("Deployment notes", "Deployment notes should document app/ as a static no-build deployment.")

    screenshot_mentions = [path for path in EXPECTED_SCREENSHOTS if path.replace("/", "\\") in evidence or path in evidence]
    if len(screenshot_mentions) == len(EXPECTED_SCREENSHOTS):
        report.pass_("Evidence screenshot refs", "All expected screenshot evidence files are referenced.")
    else:
        missing = sorted(set(EXPECTED_SCREENSHOTS) - set(screenshot_mentions))
        report.fail("Evidence screenshot refs", "Missing evidence references: " + ", ".join(missing))

    screenshot_errors = []
    for screenshot in EXPECTED_SCREENSHOTS:
        path = root / screenshot
        if not path.is_file():
            screenshot_errors.append(f"{screenshot} missing")
            continue
        if path.stat().st_size < 20_000:
            screenshot_errors.append(f"{screenshot} too small")
            continue
        with path.open("rb") as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                screenshot_errors.append(f"{screenshot} not a PNG")
    if screenshot_errors:
        report.fail("Screenshot files", "; ".join(screenshot_errors))
    else:
        report.pass_("Screenshot files", f"{len(EXPECTED_SCREENSHOTS)} PNG evidence screenshots are present and non-empty.")

    trello_terms = ["Backlog", "Sprint 1", "Sprint 5", "Done", "Blocked"]
    if all(term in evidence and term in checklist for term in trello_terms):
        report.pass_("Trello structure docs", "Sprint board lists are documented in both checklist and evidence.")
    else:
        report.fail("Trello structure docs", "Expected Trello list names are not fully documented.")


def fetch_url(url: str, timeout: float = 15.0) -> tuple[int | None, bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "shanghai-15mc-validator/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:
            body = b""
        return exc.code, body, None
    except urllib.error.URLError as exc:
        return None, b"", str(exc)


def check_online(report: Report, manifest: dict[str, Any] | None) -> None:
    if not isinstance(manifest, dict):
        report.fail("Online checks", "Cannot run online checks without a valid local manifest.")
        return

    external = manifest.get("external_platform_status", {})
    if not isinstance(external, dict):
        report.fail("Online checks", "Manifest does not contain external_platform_status.")
        return

    github_url = external.get("github_repository")
    app_url = external.get("public_deployment_url")
    trello_url = external.get("trello_shared_board")

    if isinstance(github_url, str):
        status, body, error = fetch_url(github_url)
        if status and 200 <= status < 300 and b"shanghai-15mc" in body:
            report.pass_("Online GitHub", f"{github_url} returned HTTP {status}.")
        elif error:
            report.fail("Online GitHub", f"Could not reach {github_url}: {error}")
        else:
            report.fail("Online GitHub", f"{github_url} returned HTTP {status}.")

    if isinstance(app_url, str):
        status, body, error = fetch_url(app_url)
        if status and 200 <= status < 300 and (b"15-Minute Shanghai" in body or b"leaflet-map" in body):
            report.pass_("Online public app", f"{app_url} returned HTTP {status} and expected app markup.")
        elif error:
            report.fail("Online public app", f"Could not reach {app_url}: {error}")
        else:
            report.fail("Online public app", f"{app_url} returned HTTP {status} without expected app markup.")

        manifest_url = urllib.parse.urljoin(app_url.rstrip("/") + "/", "data/project_manifest.json")
        status, body, error = fetch_url(manifest_url)
        if status and 200 <= status < 300:
            try:
                remote_manifest = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                report.fail("Online manifest", f"{manifest_url} returned invalid JSON: {exc}")
            else:
                local_summary = {
                    "feature_count": manifest.get("feature_count"),
                    "grid_cell_count": manifest.get("grid_cell_count"),
                    "external_platform_status": manifest.get("external_platform_status"),
                }
                remote_summary = {
                    "feature_count": remote_manifest.get("feature_count"),
                    "grid_cell_count": remote_manifest.get("grid_cell_count"),
                    "external_platform_status": remote_manifest.get("external_platform_status"),
                }
                if remote_summary == local_summary:
                    report.pass_("Online manifest", f"{manifest_url} matches local counts and platform links.")
                else:
                    report.fail("Online manifest", f"{manifest_url} is reachable but differs from local counts/platform links.")
        elif error:
            report.fail("Online manifest", f"Could not reach {manifest_url}: {error}")
        else:
            report.fail("Online manifest", f"{manifest_url} returned HTTP {status}.")

    if isinstance(trello_url, str):
        status, _body, error = fetch_url(trello_url)
        if status and 200 <= status < 400:
            report.pass_("Online Trello URL", f"{trello_url} returned HTTP {status}.")
        elif status in {401, 403}:
            report.warn("Online Trello URL", f"{trello_url} returned HTTP {status}; this may be expected for a private board shared with the instructor.")
        elif error:
            report.warn("Online Trello URL", f"Could not reach {trello_url}: {error}")
        else:
            report.warn("Online Trello URL", f"{trello_url} returned HTTP {status}; verify sharing manually if needed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Shanghai 15MC delivery evidence.")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root to validate. Defaults to the repository root inferred from this script.",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Also fetch GitHub, public app, public manifest, and Trello URLs.",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    report = Report()

    if not root.is_dir():
        print(f"Project root does not exist: {root}", file=sys.stderr)
        return 1

    check_static_app(report, root)
    payload, manifest = check_payload(report, root)
    check_manifest(report, root, payload, manifest)
    check_notebooks(report, root)
    check_documents_and_evidence(report, root)
    if args.online:
        check_online(report, manifest)

    report.print()

    if report.has_failures():
        return 1
    if args.strict_warnings and report.has_warnings():
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
