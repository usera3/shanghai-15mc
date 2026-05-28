from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import h3
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from scipy.signal import fftconvolve
from shapely import centroid, contains_xy, from_wkb, get_x, get_y, length
from shapely.geometry import box, shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
RAW_CACHE_DIR = ROOT / "data" / "raw"
RAW_DIR = Path(os.environ.get("SHANGHAI_15MC_RAW_DIR", RAW_CACHE_DIR))
POI_2024_CLASSIFIED_DIR = ROOT / "data" / "raw" / "poi_2024" / "POI 2024" / "csv格式" / "已分类"
BOUNDARY_URL = "https://geo.datav.aliyun.com/areas_v3/bound/310000.json"
APARTMENT_PARQUET = Path(os.environ.get("SHANGHAI_15MC_APARTMENT_PATH", RAW_CACHE_DIR / "anjuke_price_distance_filtered.parquet"))
if not APARTMENT_PARQUET.exists():
    APARTMENT_PARQUET = WORKSPACE_ROOT / "anjuke_price_distance_filtered.parquet"
ROADS_PATH = Path(os.environ.get("SHANGHAI_15MC_ROADS_PATH", RAW_CACHE_DIR / "shanghai-roads-simplified.parquet"))
if not ROADS_PATH.exists():
    ROADS_PATH = RAW_DIR / "shanghai-roads-simplified.parquet"

PROCESSED_DIR = ROOT / "data" / "processed"
APP_DATA_DIR = ROOT / "app" / "data"

GRID_JSON = PROCESSED_DIR / "shanghai_grid_seed.json"
GRID_GEOJSON = PROCESSED_DIR / "shanghai_grid_seed.geojson"
SEED_GEOJSON = PROCESSED_DIR / "shanghai_h3_seed.geojson"
SEED_JSON = PROCESSED_DIR / "shanghai_h3_seed.json"
APP_JSON = APP_DATA_DIR / "shanghai_h3_seed_min.json"
MANIFEST_JSON = PROCESSED_DIR / "project_manifest.json"
APP_MANIFEST = APP_DATA_DIR / "project_manifest.json"
ENV_LAYERS_JSON = PROCESSED_DIR / "shanghai_environment_layers.json"
NETWORK_ACCESS_JSON = PROCESSED_DIR / "shanghai_network_accessibility_grid.json"
BOUNDARY_CACHE_JSON = RAW_CACHE_DIR / "shanghai_boundary_310000.json"

GRID_CELL_M = 500
H3_RES = 8
H3_NEIGHBOR_DEPTH = 2
MODE_SPEEDS_M_S = {
    "walk": 1.33,
    "bike": 3.05,
    "transit": 4.5,
    "car": 8.3,
}
NETWORK_MODES = ["walk", "bike"]
NETWORK_BASELINE_CATEGORIES = ["school", "healthcare", "grocery", "convenience", "park", "transit"]
NETWORK_TRACK_CATEGORIES = ["fitness", "park", "grocery"]

SOURCE_PROVENANCE = [
    {
        "id": "anjuke_sale_price_proxy",
        "source": "UTSEUS-anjuke-real-estate.csv",
        "type": "housing listings",
        "role": "Sale-price and subway-distance proxy for affordability and access context.",
        "collection_date": "Provided with project files on 2026-05-24; original scrape date not encoded in the file name.",
        "processing_note": "Pre-filtered to anjuke_price_distance_filtered.parquet before scoring.",
    },
    {
        "id": "poi_2024_classified",
        "source": "POI 2024.zip classified Shanghai CSV extracts",
        "type": "amenity POI archive",
        "role": "Primary baseline and Track A amenity layer.",
        "collection_date": "Archive provided on 2026-05-24; POI update_time values in sampled files are mainly 2024 records.",
        "processing_note": "Uses bigType, midType, and smallType filters documented in poi_2024_mapping_notes.md.",
    },
    {
        "id": "shanghai_roads_simplified",
        "source": "shanghai-roads-simplified.parquet",
        "type": "road network extract",
        "role": "Walk/bike edge availability and nearest-amenity network access cache.",
        "collection_date": "Provided with project files on 2026-05-24; original extraction date not encoded in the file name.",
        "processing_note": "Uses foot and bicycle flags plus graph edges for sparse Dijkstra accessibility.",
    },
    {
        "id": "shanghai_boundary",
        "source": "Aliyun DataV GeoAtlas 310000 boundary",
        "type": "municipal boundary",
        "role": "Shanghai clipping boundary and 500 m grid extent.",
        "collection_date": "Fetched or refreshed during local pipeline execution.",
        "processing_note": "Cached locally at data/raw/shanghai_boundary_310000.json for reproducibility.",
    },
    {
        "id": "environment_layers",
        "source": "Cached AQI and Sentinel-2 NDVI proxy layers",
        "type": "environmental indicators",
        "role": "Track A environmental quality and greenery inputs.",
        "collection_date": "Cached locally during the 2026-05-24 prototype build.",
        "processing_note": "Attached as district / sampled proxy surfaces, not as high-resolution per-pixel remote-sensing analysis.",
    },
]


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_boundary():
    try:
        with urlopen(BOUNDARY_URL, timeout=30) as resp:
            geojson = json.load(resp)
        BOUNDARY_CACHE_JSON.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
    except Exception:
        if not BOUNDARY_CACHE_JSON.exists():
            raise
        geojson = json.loads(BOUNDARY_CACHE_JSON.read_text(encoding="utf-8"))
    if geojson.get("type") != "FeatureCollection" or "features" not in geojson:
        raise ValueError(f"Invalid cached boundary file: {BOUNDARY_CACHE_JSON}")
    geometries = [shape(feature["geometry"]) for feature in geojson["features"]]
    return unary_union(geometries)


def normalize(series: pd.Series) -> pd.Series:
    series = series.fillna(0).astype(float)
    if len(series) == 0:
        return series
    upper = float(series.quantile(0.95))
    if upper <= 0:
        upper = float(series.max())
    if upper <= 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return series.clip(0, upper) / upper


def normalize_observed(series: pd.Series, observed: pd.Series | None = None) -> pd.Series:
    series = series.astype(float)
    mask = series.notna() if observed is None else observed.fillna(False).astype(bool) & series.notna()
    result = pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    if not mask.any():
        return result
    values = series.loc[mask].clip(lower=0)
    upper = float(values.quantile(0.95))
    if upper <= 0:
        upper = float(values.max())
    if upper <= 0:
        return result
    result.loc[mask] = values.clip(0, upper) / upper
    return result


def mean_score(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return df[columns].mean(axis=1)


def h3_index_from_lonlat(lon: np.ndarray, lat: np.ndarray) -> list[str]:
    return [h3.latlng_to_cell(float(lat_i), float(lon_i), H3_RES) for lon_i, lat_i in zip(lon, lat)]


def build_grid(boundary) -> pd.DataFrame:
    to_4576 = Transformer.from_crs(4326, 4576, always_xy=True)
    to_4326 = Transformer.from_crs(4576, 4326, always_xy=True)

    def project_geom_to_4576(geom):
        if geom.geom_type == "Polygon":
            exterior = np.array(geom.exterior.coords)
            bx, by = to_4576.transform(exterior[:, 0], exterior[:, 1])
            holes = []
            for interior in geom.interiors:
                coords = np.array(interior.coords)
                ix, iy = to_4576.transform(coords[:, 0], coords[:, 1])
                holes.append(list(map(list, zip(ix, iy))))
            return shape({"type": "Polygon", "coordinates": [list(map(list, zip(bx, by))), *holes]})
        if geom.geom_type == "MultiPolygon":
            return unary_union([project_geom_to_4576(part) for part in geom.geoms])
        raise ValueError(f"Unsupported boundary geometry: {geom.geom_type}")

    boundary_4576 = project_geom_to_4576(boundary)

    minx, miny, maxx, maxy = boundary_4576.bounds
    rows = []
    grid_id = 0
    for x0 in np.arange(minx, maxx, GRID_CELL_M):
        for y0 in np.arange(miny, maxy, GRID_CELL_M):
            cell = box(x0, y0, x0 + GRID_CELL_M, y0 + GRID_CELL_M)
            clipped = cell.intersection(boundary_4576)
            if clipped.is_empty:
                continue
            c = clipped.centroid
            lon, lat = to_4326.transform(c.x, c.y)
            if not contains_xy(boundary, np.array([lon]), np.array([lat]))[0]:
                continue
            rows.append(
                {
                    "grid_id": f"grid_{grid_id:05d}",
                    "x_idx": int(round((x0 - minx) / GRID_CELL_M)),
                    "y_idx": int(round((y0 - miny) / GRID_CELL_M)),
                    "cell_x0_m": float(x0),
                    "cell_y0_m": float(y0),
                    "center_x_m": float(c.x),
                    "center_y_m": float(c.y),
                    "center_lon": float(lon),
                    "center_lat": float(lat),
                    "geometry_xy": clipped.wkt,
                    "cell_area_m2": float(clipped.area),
                }
            )
            grid_id += 1
    grid = pd.DataFrame(rows)
    grid["h3"] = h3_index_from_lonlat(grid["center_lon"].to_numpy(), grid["center_lat"].to_numpy())
    return grid


def load_apartment_hex_stats() -> pd.DataFrame:
    df = pd.read_parquet(APARTMENT_PARQUET)
    df["h3"] = h3_index_from_lonlat(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    grouped = (
        df.groupby("h3")
        .agg(
            apartment_count=("longitude", "size"),
            avg_price_m2=("onesquaremeter", "mean"),
            median_price_m2=("onesquaremeter", "median"),
            avg_subway_distance_m=("distances", "mean"),
            median_subway_distance_m=("distances", "median"),
        )
        .reset_index()
    )
    return grouped


def _increment_counts(frame: pd.DataFrame, mask: pd.Series, key: str, counters: dict[str, defaultdict[str, int]]) -> None:
    subset = frame.loc[mask, "h3"]
    if subset.empty:
        return
    counts = subset.value_counts()
    bucket = counters[key]
    for h3_id, count in counts.items():
        bucket[h3_id] += int(count)


def build_poi_2024_hex_counts(boundary) -> pd.DataFrame:
    counters: dict[str, defaultdict[str, int]] = {
        "subway_exit_count": defaultdict(int),
        "subway_station_count": defaultdict(int),
        "bus_stop_count": defaultdict(int),
        "school_count": defaultdict(int),
        "healthcare_count": defaultdict(int),
        "pharmacy_count": defaultdict(int),
        "grocery_count": defaultdict(int),
        "convenience_count": defaultdict(int),
        "park_count": defaultdict(int),
        "gym_count": defaultdict(int),
        "basketball_count": defaultdict(int),
        "swimming_count": defaultdict(int),
    }

    file_specs = {
        "transport": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-交通设施服务.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
        "health": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-医疗保健服务.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
        "education": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-科教文化服务.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
        "shopping": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-购物服务.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
        "parks": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-风景名胜.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
        "sport": {
            "path": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-体育休闲服务.csv",
            "usecols": ["midType", "smallType", "wgs84Lng", "wgs84Lat"],
        },
    }

    for key, spec in file_specs.items():
        chunks = pd.read_csv(spec["path"], usecols=spec["usecols"], chunksize=200_000)
        for chunk in chunks:
            chunk = chunk.dropna(subset=["wgs84Lng", "wgs84Lat"]).copy()
            if chunk.empty:
                continue

            inside = contains_xy(boundary, chunk["wgs84Lng"].to_numpy(), chunk["wgs84Lat"].to_numpy())
            chunk = chunk[inside].copy()
            if chunk.empty:
                continue

            chunk["h3"] = h3_index_from_lonlat(chunk["wgs84Lng"].to_numpy(), chunk["wgs84Lat"].to_numpy())
            mid = chunk["midType"].fillna("")
            small = chunk["smallType"].fillna("")

            if key == "transport":
                _increment_counts(chunk, mid.eq("地铁站") & small.eq("出入口"), "subway_exit_count", counters)
                _increment_counts(chunk, mid.eq("地铁站") & small.eq("地铁站"), "subway_station_count", counters)
                _increment_counts(chunk, mid.eq("公交车站"), "bus_stop_count", counters)
            elif key == "health":
                healthcare_mask = mid.isin(["综合医院", "专科医院", "诊所", "医疗保健服务场所", "急救中心", "疾病预防机构"]) & ~small.isin(["药房", "宠物诊所"])
                pharmacy_mask = small.eq("药房")
                _increment_counts(chunk, healthcare_mask, "healthcare_count", counters)
                _increment_counts(chunk, pharmacy_mask, "pharmacy_count", counters)
            elif key == "education":
                school_mask = mid.eq("学校") | small.isin(["幼儿园", "小学", "中学", "高等院校", "职业技术学校", "学校"])
                _increment_counts(chunk, school_mask, "school_count", counters)
            elif key == "shopping":
                grocery_mask = mid.isin(["便民商店/便利店", "综合市场", "超级市场"]) | small.isin(["便民商店/便利店", "超市", "农副产品市场", "果品市场"])
                convenience_mask = mid.eq("便民商店/便利店") | small.eq("便民商店/便利店")
                _increment_counts(chunk, grocery_mask, "grocery_count", counters)
                _increment_counts(chunk, convenience_mask, "convenience_count", counters)
            elif key == "parks":
                park_mask = mid.eq("公园广场") | small.isin(["公园", "植物园", "城市广场"])
                _increment_counts(chunk, park_mask, "park_count", counters)
            elif key == "sport":
                _increment_counts(chunk, small.eq("健身中心"), "gym_count", counters)
                _increment_counts(chunk, small.eq("篮球场馆"), "basketball_count", counters)
                _increment_counts(chunk, small.eq("游泳馆"), "swimming_count", counters)

    frames = []
    for key, bucket in counters.items():
        if bucket:
            frames.append(pd.DataFrame({"h3": list(bucket.keys()), key: list(bucket.values())}))

    merged = None
    for frame in frames:
        merged = frame if merged is None else merged.merge(frame, on="h3", how="outer")
    return pd.DataFrame({"h3": []}) if merged is None else merged.fillna(0)


def build_road_hex_metrics(boundary) -> pd.DataFrame:
    roads = pd.read_parquet(ROADS_PATH, columns=["bicycle", "foot", "geometry"])
    geom = from_wkb(roads["geometry"].to_numpy())
    centroids = centroid(geom)
    lengths_m = length(geom)

    transformer = Transformer.from_crs(4576, 4326, always_xy=True)
    lon, lat = transformer.transform(get_x(centroids), get_y(centroids))
    inside = contains_xy(boundary, lon, lat)

    roads = roads[inside].copy()
    roads["length_m"] = lengths_m[inside]
    roads["longitude"] = np.asarray(lon)[inside]
    roads["latitude"] = np.asarray(lat)[inside]
    roads["h3"] = h3_index_from_lonlat(roads["longitude"].to_numpy(), roads["latitude"].to_numpy())
    roads["bike_length_km"] = np.where(roads["bicycle"] > 0, roads["length_m"] / 1000.0, 0.0)
    roads["walk_length_km"] = np.where(roads["foot"] > 0, roads["length_m"] / 1000.0, 0.0)

    grouped = (
        roads.groupby("h3")
        .agg(
            bike_length_km=("bike_length_km", "sum"),
            walk_length_km=("walk_length_km", "sum"),
            bike_edge_count=("bicycle", lambda s: int((s > 0).sum())),
            walk_edge_count=("foot", lambda s: int((s > 0).sum())),
        )
        .reset_index()
    )
    return grouped


def _append_category_points(
    frame: pd.DataFrame,
    mask: pd.Series,
    category: str,
    rows: list[dict[str, float | str]],
) -> None:
    subset = frame.loc[mask, ["wgs84Lng", "wgs84Lat"]].dropna()
    if subset.empty:
        return
    rows.extend(
        {
            "category": category,
            "lon": float(row.wgs84Lng),
            "lat": float(row.wgs84Lat),
        }
        for row in subset.itertuples(index=False)
    )


def build_network_poi_points(boundary) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    file_specs = {
        "transport": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-交通设施服务.csv",
        "health": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-医疗保健服务.csv",
        "education": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-科教文化服务.csv",
        "shopping": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-购物服务.csv",
        "parks": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-风景名胜.csv",
        "sport": POI_2024_CLASSIFIED_DIR / "上海市-1754933-utf8.csv-体育休闲服务.csv",
    }

    for key, path in file_specs.items():
        chunks = pd.read_csv(path, usecols=["midType", "smallType", "wgs84Lng", "wgs84Lat"], chunksize=200_000)
        for chunk in chunks:
            chunk = chunk.dropna(subset=["wgs84Lng", "wgs84Lat"]).copy()
            if chunk.empty:
                continue
            inside = contains_xy(boundary, chunk["wgs84Lng"].to_numpy(), chunk["wgs84Lat"].to_numpy())
            chunk = chunk[inside].copy()
            if chunk.empty:
                continue

            mid = chunk["midType"].fillna("")
            small = chunk["smallType"].fillna("")

            if key == "transport":
                _append_category_points(chunk, mid.eq("地铁站") | mid.eq("公交车站"), "transit", rows)
            elif key == "health":
                healthcare_mask = mid.isin(["综合医院", "专科医院", "诊所", "医疗保健服务场所", "急救中心", "疾病预防机构"]) & ~small.isin(["药房", "宠物诊所"])
                _append_category_points(chunk, healthcare_mask, "healthcare", rows)
            elif key == "education":
                school_mask = mid.eq("学校") | small.isin(["幼儿园", "小学", "中学", "高等院校", "职业技术学校", "学校"])
                _append_category_points(chunk, school_mask, "school", rows)
            elif key == "shopping":
                grocery_mask = mid.isin(["综合市场", "超级市场"]) | small.isin(["超市", "农副产品市场", "果品市场", "蔬菜市场", "水产海鲜市场"])
                convenience_mask = mid.eq("便民商店/便利店") | small.eq("便民商店/便利店")
                _append_category_points(chunk, grocery_mask, "grocery", rows)
                _append_category_points(chunk, convenience_mask, "convenience", rows)
            elif key == "parks":
                park_mask = mid.eq("公园广场") | small.isin(["公园", "植物园", "城市广场"])
                _append_category_points(chunk, park_mask, "park", rows)
            elif key == "sport":
                fitness_mask = small.str.contains("健身|篮球|游泳|羽毛球|网球|足球|体育馆|运动场|户外健身|跆拳道", regex=True, na=False)
                _append_category_points(chunk, fitness_mask, "fitness", rows)

    points = pd.DataFrame(rows)
    if points.empty:
        return pd.DataFrame(columns=["category", "lon", "lat"])
    return points.drop_duplicates().reset_index(drop=True)


def build_network_graph_inputs(boundary):
    roads = pd.read_parquet(ROADS_PATH, columns=["u", "v", "bicycle", "foot", "geometry"])
    geom = from_wkb(roads["geometry"].to_numpy())
    centroids = centroid(geom)
    lengths_m = length(geom)

    transformer = Transformer.from_crs(4576, 4326, always_xy=True)
    lon, lat = transformer.transform(get_x(centroids), get_y(centroids))
    inside = contains_xy(boundary, lon, lat)

    roads = roads.loc[inside].copy()
    roads["length_m"] = lengths_m[inside]

    node_ids = pd.Index(pd.unique(pd.concat([roads["u"], roads["v"]], ignore_index=True)))
    node_index = pd.Series(np.arange(len(node_ids), dtype=np.int32), index=node_ids)

    row_idx = node_index.loc[roads["u"]].to_numpy(dtype=np.int32)
    col_idx = node_index.loc[roads["v"]].to_numpy(dtype=np.int32)
    lengths = roads["length_m"].to_numpy(dtype=float)

    def graph_for(mask: np.ndarray):
        rows = np.concatenate([row_idx[mask], col_idx[mask]])
        cols = np.concatenate([col_idx[mask], row_idx[mask]])
        data = np.concatenate([lengths[mask], lengths[mask]])
        return csr_matrix((data, (rows, cols)), shape=(len(node_ids), len(node_ids)))

    graphs = {
        "walk": graph_for(roads["foot"].to_numpy() > 0),
        "bike": graph_for(roads["bicycle"].to_numpy() > 0),
    }

    endpoints = pd.concat(
        [
            roads[["u"]].rename(columns={"u": "node_id"}),
            roads[["v"]].rename(columns={"v": "node_id"}),
        ],
        ignore_index=True,
    ).drop_duplicates()
    endpoints["idx"] = node_index.loc[endpoints["node_id"]].to_numpy(dtype=np.int32)

    geom_coords = from_wkb(roads["geometry"].to_numpy())
    start_points = []
    end_points = []
    for line in geom_coords:
        coords = np.asarray(line.coords)
        start_points.append(coords[0])
        end_points.append(coords[-1])

    coord_rows = pd.concat(
        [
            roads[["u"]].rename(columns={"u": "node_id"}).assign(x=[p[0] for p in start_points], y=[p[1] for p in start_points]),
            roads[["v"]].rename(columns={"v": "node_id"}).assign(x=[p[0] for p in end_points], y=[p[1] for p in end_points]),
        ],
        ignore_index=True,
    ).drop_duplicates("node_id")
    coord_rows["idx"] = node_index.loc[coord_rows["node_id"]].to_numpy(dtype=np.int32)
    coord_rows = coord_rows.sort_values("idx")

    tree = cKDTree(coord_rows[["x", "y"]].to_numpy(dtype=float))
    return graphs, tree, coord_rows


def build_network_accessibility_grid(grid_df: pd.DataFrame, boundary) -> pd.DataFrame:
    if NETWORK_ACCESS_JSON.exists():
        cached = pd.read_json(NETWORK_ACCESS_JSON)
        if set(["grid_id", "network_access_walk", "network_access_bike"]).issubset(cached.columns) and len(cached) == len(grid_df):
            return cached

    print("Building road-network accessibility cache…")
    graphs, node_tree, _ = build_network_graph_inputs(boundary)
    poi_points = build_network_poi_points(boundary)

    grid_xy = grid_df[["center_x_m", "center_y_m"]].to_numpy(dtype=float)
    _, grid_node_idx = node_tree.query(grid_xy, k=1)

    to_4576 = Transformer.from_crs(4326, 4576, always_xy=True)
    rows = pd.DataFrame({"grid_id": grid_df["grid_id"].to_numpy()})

    for mode in NETWORK_MODES:
        graph = graphs[mode]
        speed = MODE_SPEEDS_M_S[mode]
        time_limit_s = 15 * 60
        distance_limit_m = speed * time_limit_s
        category_scores = []

        for category in sorted(set(NETWORK_BASELINE_CATEGORIES + NETWORK_TRACK_CATEGORIES)):
            print(f"  {mode}: nearest {category} by network distance…")
            subset = poi_points[poi_points["category"] == category]
            if subset.empty:
                network_distance = np.full(len(grid_df), np.inf)
                network_score = np.zeros(len(grid_df))
            else:
                poi_x, poi_y = to_4576.transform(subset["lon"].to_numpy(dtype=float), subset["lat"].to_numpy(dtype=float))
                _, poi_node_idx = node_tree.query(np.column_stack([poi_x, poi_y]), k=1)
                source_idx = np.unique(poi_node_idx.astype(np.int32))
                distances = dijkstra(graph, directed=False, indices=source_idx, min_only=True, limit=distance_limit_m)
                network_distance = distances[grid_node_idx]
                network_score = np.where(
                    np.isfinite(network_distance),
                    np.clip(1 - (network_distance / distance_limit_m), 0, 1),
                    0,
                )

            rows[f"network_dist_m_{mode}_{category}"] = np.where(np.isfinite(network_distance), network_distance, np.nan)
            rows[f"network_reach_{mode}_{category}"] = network_score
            category_scores.append(f"network_reach_{mode}_{category}")

        baseline_cols = [f"network_reach_{mode}_{category}" for category in NETWORK_BASELINE_CATEGORIES]
        track_cols = [f"network_reach_{mode}_{category}" for category in NETWORK_TRACK_CATEGORIES]
        rows[f"network_access_{mode}"] = 100 * rows[baseline_cols].mean(axis=1)
        rows[f"network_track_access_{mode}"] = 100 * rows[track_cols].mean(axis=1)

    NETWORK_ACCESS_JSON.write_text(rows.to_json(orient="records", force_ascii=False), encoding="utf-8")
    return rows


def score_h3_hexes(apartments: pd.DataFrame, poi: pd.DataFrame, roads: pd.DataFrame) -> pd.DataFrame:
    df = apartments.merge(poi, on="h3", how="outer").merge(roads, on="h3", how="outer")
    df["has_housing_sample"] = df["apartment_count"].fillna(0) > 0

    df["distance_inverse_norm"] = np.where(
        df["has_housing_sample"],
        1 - normalize_observed(df["avg_subway_distance_m"], df["has_housing_sample"]),
        0,
    )
    df["price_affordability_norm"] = np.where(
        df["has_housing_sample"],
        1 - normalize_observed(df["avg_price_m2"], df["has_housing_sample"]),
        0,
    )

    metric_map = {
        "school_norm": "school_count",
        "healthcare_norm": "healthcare_count",
        "pharmacy_norm": "pharmacy_count",
        "grocery_norm": "grocery_count",
        "convenience_norm": "convenience_count",
        "park_norm": "park_count",
        "subway_norm": "subway_exit_count",
        "bus_norm": "bus_stop_count",
        "gym_norm": "gym_count",
        "basketball_norm": "basketball_count",
        "swimming_norm": "swimming_count",
        "bike_km_norm": "bike_length_km",
        "walk_km_norm": "walk_length_km",
    }
    count_cols = sorted({*metric_map.values(), "apartment_count"})
    for col in count_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    for out_col, src_col in metric_map.items():
        df[out_col] = normalize(df[src_col])

    df["transit_norm"] = mean_score(df, ["subway_norm", "bus_norm", "distance_inverse_norm"])
    df["health_bundle_norm"] = mean_score(df, ["healthcare_norm", "pharmacy_norm"])
    df["grocery_bundle_norm"] = mean_score(df, ["grocery_norm", "convenience_norm"])
    df["fitness_bundle_norm"] = mean_score(df, ["gym_norm", "basketball_norm", "swimming_norm"])

    df["score_baseline_walk"] = 100 * mean_score(
        df,
        ["school_norm", "health_bundle_norm", "grocery_bundle_norm", "park_norm", "convenience_norm", "transit_norm"],
    )
    df["score_baseline_bike"] = 100 * mean_score(
        df,
        ["school_norm", "health_bundle_norm", "grocery_bundle_norm", "park_norm", "transit_norm", "bike_km_norm"],
    )
    df["score_baseline_transit"] = 100 * mean_score(
        df,
        ["school_norm", "health_bundle_norm", "grocery_bundle_norm", "convenience_norm", "transit_norm", "park_norm"],
    )
    df["score_baseline_car"] = 100 * mean_score(
        df,
        ["school_norm", "health_bundle_norm", "grocery_bundle_norm", "park_norm", "convenience_norm", "walk_km_norm"],
    )

    df["score_track_walk"] = 100 * mean_score(df, ["fitness_bundle_norm", "park_norm", "grocery_bundle_norm", "walk_km_norm"])
    df["score_track_bike"] = 100 * mean_score(df, ["fitness_bundle_norm", "park_norm", "bike_km_norm", "grocery_bundle_norm"])
    df["score_track_transit"] = 100 * mean_score(df, ["fitness_bundle_norm", "transit_norm", "park_norm", "grocery_bundle_norm"])
    df["score_track_car"] = 100 * mean_score(df, ["fitness_bundle_norm", "park_norm", "walk_km_norm", "price_affordability_norm"])

    for mode in ["walk", "bike", "transit", "car"]:
        df[f"score_composite_{mode}"] = 0.6 * df[f"score_baseline_{mode}"] + 0.4 * df[f"score_track_{mode}"]

    df["housing_band"] = pd.cut(
        df["avg_price_m2"],
        bins=[-np.inf, 35_000, 55_000, 80_000, np.inf],
        labels=["budget proxy", "mid-range proxy", "high-cost proxy", "premium proxy"],
    ).astype(str)
    df.loc[~df["has_housing_sample"], "housing_band"] = "no housing sample"
    df[["avg_price_m2", "median_price_m2", "avg_subway_distance_m", "median_subway_distance_m"]] = df[
        ["avg_price_m2", "median_price_m2", "avg_subway_distance_m", "median_subway_distance_m"]
    ].fillna(0)

    labels = []
    for _, row in df.iterrows():
        candidates = {
            "schools": row["school_count"],
            "healthcare": row["healthcare_count"],
            "groceries": row["grocery_count"],
            "parks": row["park_count"],
            "transit": row["subway_exit_count"] + row["bus_stop_count"],
            "fitness": row["gym_count"] + row["basketball_count"] + row["swimming_count"],
        }
        top = [name for name, value in sorted(candidates.items(), key=lambda item: item[1], reverse=True) if value > 0][:3]
        labels.append(", ".join(top) if top else "low recorded amenity mix")
    df["top_amenities"] = labels
    return df


def attach_hex_metrics_to_grid(grid: pd.DataFrame, hex_df: pd.DataFrame) -> pd.DataFrame:
    merged = grid.merge(hex_df, on="h3", how="left")
    if "has_housing_sample" not in merged.columns:
        merged["has_housing_sample"] = False
    merged["has_housing_sample"] = merged["has_housing_sample"].fillna(False).astype(bool)
    if "housing_band" not in merged.columns:
        merged["housing_band"] = "no housing sample"
    merged["housing_band"] = merged["housing_band"].fillna("no housing sample")
    text_cols = ["top_amenities", "housing_band"]
    numeric_cols = [col for col in merged.columns if col not in {"geometry_xy", "h3", "grid_id", *text_cols}]
    merged[numeric_cols] = merged[numeric_cols].fillna(0)
    return merged


def attach_environment_layers(grid_df: pd.DataFrame) -> pd.DataFrame:
    if not ENV_LAYERS_JSON.exists():
        return grid_df

    payload = json.loads(ENV_LAYERS_JSON.read_text(encoding="utf-8"))
    df = grid_df.copy()
    df["aqi_lon_round"] = df["center_lon"].round(1)
    df["aqi_lat_round"] = df["center_lat"].round(1)
    df["ndvi_lon_round"] = df["center_lon"].round(2)
    df["ndvi_lat_round"] = df["center_lat"].round(2)

    aqi_df = pd.DataFrame(payload.get("aqi", []))
    ndvi_df = pd.DataFrame(payload.get("ndvi", []))
    if not aqi_df.empty:
        df = df.merge(aqi_df, on=["aqi_lon_round", "aqi_lat_round"], how="left")
    if not ndvi_df.empty:
        df = df.merge(ndvi_df, on=["ndvi_lon_round", "ndvi_lat_round"], how="left")

    df["european_aqi"] = df.get("european_aqi", pd.Series(dtype=float)).fillna(df.get("european_aqi", pd.Series(dtype=float)).median() if "european_aqi" in df else 0)
    df["ndvi"] = df.get("ndvi", pd.Series(dtype=float)).fillna(df.get("ndvi", pd.Series(dtype=float)).median() if "ndvi" in df else 0)
    df["aqi_norm"] = 1 - normalize(df["european_aqi"])
    df["ndvi_norm"] = normalize(df["ndvi"])
    return df


def build_isochrone_proxy_scores(grid_df: pd.DataFrame) -> pd.DataFrame:
    df = grid_df.copy()
    x_max = int(df["x_idx"].max())
    y_max = int(df["y_idx"].max())
    grid_shape = (y_max + 1, x_max + 1)

    def to_array(values: pd.Series) -> np.ndarray:
        arr = np.zeros(grid_shape, dtype=float)
        arr[df["y_idx"].to_numpy(), df["x_idx"].to_numpy()] = values.to_numpy(dtype=float)
        return arr

    def extract(arr: np.ndarray) -> np.ndarray:
        return arr[df["y_idx"].to_numpy(), df["x_idx"].to_numpy()]

    walk_need = to_array(mean_score(df, ["school_norm", "health_bundle_norm", "grocery_bundle_norm", "park_norm", "convenience_norm", "distance_inverse_norm"]))
    bike_need = to_array(mean_score(df, ["school_norm", "grocery_bundle_norm", "fitness_bundle_norm", "park_norm", "bike_km_norm", "distance_inverse_norm"]))
    transit_need = to_array(mean_score(df, ["transit_norm", "school_norm", "health_bundle_norm", "grocery_bundle_norm", "convenience_norm", "distance_inverse_norm"]))
    car_need = to_array(mean_score(df, ["walk_km_norm", "grocery_bundle_norm", "health_bundle_norm", "park_norm", "price_affordability_norm", "distance_inverse_norm"]))

    weight_map = {
        "walk": walk_need,
        "bike": bike_need,
        "transit": transit_need,
        "car": car_need,
    }

    for mode, speed in MODE_SPEEDS_M_S.items():
        radius_m = speed * 15 * 60
        radius_cells = max(1, int(np.ceil(radius_m / GRID_CELL_M)))
        yy, xx = np.ogrid[-radius_cells : radius_cells + 1, -radius_cells : radius_cells + 1]
        disk = (xx**2 + yy**2) <= radius_cells**2
        kernel = disk.astype(float)
        kernel /= kernel.sum()
        score_surface = fftconvolve(weight_map[mode], kernel, mode="same")
        df[f"proxy_access_{mode}"] = 100 * extract(score_surface)
        df[f"isochrone_radius_m_{mode}"] = radius_m

    if "ndvi_norm" not in df.columns:
        df["ndvi_norm"] = 0.0
    if "aqi_norm" not in df.columns:
        df["aqi_norm"] = 0.0

    for mode in ["walk", "bike"]:
        network_col = f"network_access_{mode}"
        network_track_col = f"network_track_access_{mode}"
        if network_col not in df.columns:
            df[network_col] = df[f"proxy_access_{mode}"]
        if network_track_col not in df.columns:
            df[network_track_col] = df[network_col]

    df["score_track_walk"] = 100 * mean_score(
        df,
        ["fitness_bundle_norm", "park_norm", "grocery_bundle_norm", "walk_km_norm", "ndvi_norm", "aqi_norm"],
    )
    df["score_track_bike"] = 100 * mean_score(
        df,
        ["fitness_bundle_norm", "park_norm", "bike_km_norm", "grocery_bundle_norm", "ndvi_norm", "aqi_norm"],
    )
    df["score_track_transit"] = 100 * mean_score(
        df,
        ["fitness_bundle_norm", "transit_norm", "park_norm", "grocery_bundle_norm", "ndvi_norm", "aqi_norm"],
    )
    df["score_track_car"] = 100 * mean_score(
        df,
        ["fitness_bundle_norm", "park_norm", "walk_km_norm", "price_affordability_norm", "ndvi_norm", "aqi_norm"],
    )

    for mode in ["walk", "bike", "transit", "car"]:
        df[f"score_composite_{mode}"] = 0.6 * df[f"score_baseline_{mode}"] + 0.4 * df[f"score_track_{mode}"]

    for mode in ["walk", "bike"]:
        df[f"score_baseline_{mode}"] = 0.65 * df[f"score_baseline_{mode}"] + 0.35 * df[f"network_access_{mode}"]
        df[f"score_track_{mode}"] = 0.6 * df[f"score_track_{mode}"] + 0.4 * df[f"network_track_access_{mode}"]
        df[f"score_composite_{mode}"] = 0.6 * df[f"score_baseline_{mode}"] + 0.4 * df[f"score_track_{mode}"]

    return df


def aggregate_grid_to_h3(grid_df: pd.DataFrame) -> pd.DataFrame:
    score_cols = [c for c in grid_df.columns if c.startswith("score_")]
    mean_cols = [
        "avg_price_m2",
        "median_price_m2",
        "avg_subway_distance_m",
        "median_subway_distance_m",
        "has_housing_sample",
        "price_affordability_norm",
        "transit_norm",
        "park_norm",
        "proxy_access_walk",
        "proxy_access_bike",
        "proxy_access_transit",
        "proxy_access_car",
        "network_access_walk",
        "network_access_bike",
        "network_track_access_walk",
        "network_track_access_bike",
        "ndvi",
        "ndvi_norm",
        "european_aqi",
        "aqi_norm",
    ]
    sum_cols = [
        "apartment_count",
        "school_count",
        "healthcare_count",
        "pharmacy_count",
        "grocery_count",
        "convenience_count",
        "park_count",
        "subway_exit_count",
        "subway_station_count",
        "bus_stop_count",
        "gym_count",
        "basketball_count",
        "swimming_count",
        "bike_length_km",
        "walk_length_km",
        "bike_edge_count",
        "walk_edge_count",
    ]

    agg_spec: dict[str, tuple[str, str]] = {"grid_cell_count": ("grid_id", "size")}
    for col in score_cols + mean_cols:
        if col in grid_df.columns:
            agg_spec[col] = (col, "max" if col == "has_housing_sample" else "mean")
    for col in sum_cols:
        if col in grid_df.columns:
            agg_spec[col] = (col, "sum")

    grouped = grid_df.groupby("h3").agg(**agg_spec).reset_index()

    grouped["housing_band"] = pd.cut(
        grouped["avg_price_m2"],
        bins=[-np.inf, 35_000, 55_000, 80_000, np.inf],
        labels=["budget proxy", "mid-range proxy", "high-cost proxy", "premium proxy"],
    ).astype(str)
    if "has_housing_sample" in grouped.columns:
        grouped["has_housing_sample"] = grouped["has_housing_sample"].astype(bool)
        grouped.loc[~grouped["has_housing_sample"], "housing_band"] = "no housing sample"

    grouped["top_amenities"] = (
        grouped[["school_count", "healthcare_count", "grocery_count", "park_count", "gym_count"]]
        .apply(
            lambda row: ", ".join(
                [
                    label
                    for label, _ in sorted(
                        {
                            "schools": row["school_count"],
                            "healthcare": row["healthcare_count"],
                            "groceries": row["grocery_count"],
                            "parks": row["park_count"],
                            "fitness": row["gym_count"],
                        }.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                    if _ > 0
                ][:3]
            )
            or "low recorded amenity mix",
            axis=1,
        )
    )
    return grouped


def build_grid_feature_collection(grid_df: pd.DataFrame) -> dict:
    to_4326 = Transformer.from_crs(4576, 4326, always_xy=True)
    features = []
    for row in grid_df.to_dict(orient="records"):
        from shapely import from_wkt

        cell = from_wkt(row["geometry_xy"])
        if cell.geom_type == "MultiPolygon":
            cell = max(cell.geoms, key=lambda geom: geom.area)
        coords = np.array(cell.exterior.coords)
        lon, lat = to_4326.transform(coords[:, 0], coords[:, 1])
        ring = [[float(x), float(y)] for x, y in zip(lon, lat)]
        props = {k: v for k, v in row.items() if k != "geometry_xy"}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_h3_feature_collection(df: pd.DataFrame) -> dict:
    features = []
    for row in df.to_dict(orient="records"):
        h3_id = row["h3"]
        boundary = h3.cell_to_boundary(h3_id)
        ring = [[lng, lat] for lat, lng in boundary]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        props = {k: v for k, v in row.items() if k != "h3"}
        props["h3_index"] = h3_id
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_manifest(grid_df: pd.DataFrame, h3_df: pd.DataFrame) -> dict:
    return {
        "project": "15-Minute Shanghai Prototype",
        "track": "Healthy Lifestyle & Sport",
        "description": "Grid-first proxy pipeline using 500m cells, 2024 classified POI extracts, and H3 aggregation.",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "h3_resolution": H3_RES,
        "grid_cell_size_m": GRID_CELL_M,
        "grid_cell_count": int(len(grid_df)),
        "feature_count": int(len(h3_df)),
        "source_files": [
            "UTSEUS-anjuke-real-estate.csv -> anjuke_price_distance_filtered.parquet",
            "POI 2024.zip classified Shanghai CSV extracts",
            "shanghai-roads-simplified.parquet",
            BOUNDARY_URL,
            "shanghai_environment_layers.json",
        ],
        "source_provenance": SOURCE_PROVENANCE,
        "method_summary": [
            "Clip Shanghai municipal boundary, project to EPSG:4576, and build a 500 m grid.",
            "Classify 2024 POIs with type fields rather than noisy keyword-only name matching.",
            "Attach housing sale-price proxy, subway-distance proxy, road metrics, environmental proxies, and POI counts to grid / H3 layers.",
            "Compute mode-specific 15-minute radius proxy surfaces using documented speed assumptions.",
            "Improve walk and bike with sparse road-network nearest-amenity access; keep transit and car as documented proxies.",
            "Aggregate cell metrics to H3 r8 for web visualization and recommendation ranking.",
        ],
        "speed_assumptions_m_s": MODE_SPEEDS_M_S,
        "score_method": {
            "normalization": "Most count / length fields are clipped at the 95th percentile and scaled to 0-1 before scoring.",
            "baseline": "Universal needs layer combines schools, healthcare, groceries, convenience, parks, transit, walk/bike support, and housing context.",
            "track": "Track A adds fitness, sport/open-space, fresh-market/healthy-food, greenery, and AQI proxy indicators.",
            "composite": "Composite score = 60% baseline + 40% Track A.",
            "walk_bike_network_blend": "Walk/bike baseline scores are blended with 35% road-network nearest-amenity access; Track A walk/bike scores use 40% network track access.",
            "housing_missingness": "H3 cells without housing samples are flagged and receive no affordability credit.",
        },
        "track_indicator_status": {
            "gym_or_fitness_studio": "Implemented from 2024 POI fitness center category.",
            "public_park_with_exercise_equipment": "Partially implemented as public park proxy; exercise-equipment tags are not separately available.",
            "running_track_sports_field_basketball": "Partially implemented through basketball and sport POI categories.",
            "public_swimming_pool": "Implemented from swimming POI category where present.",
            "yoga_martial_arts_dance": "Partially represented inside broader fitness / sport POI categories.",
            "dedicated_cycling_lane_length": "Approximated with simplified road bicycle availability, not audited protected lane data.",
            "fresh_market_health_food": "Implemented with grocery, market, supermarket, and fresh-food POI proxies.",
            "ndvi": "Implemented as cached Sentinel-2 NDVI proxy surface.",
            "aqi": "Implemented as cached AQI proxy surface.",
        },
        "external_platform_status": {
            "github_repository": "https://github.com/usera3/shanghai-15mc",
            "public_deployment_url": "https://usera3.github.io/shanghai-15mc/",
            "trello_shared_board": "https://trello.com/b/ehvAvB4n/15mc-shanghai-mozi",
            "trello_instructor_invited": True,
        },
        "limitations": [
            "Scores are still proxy indicators, not full network isochrone results from routing engines.",
            "The current app uses sale-price data as an affordability proxy instead of true rent listings.",
            "Transit mode currently uses stop density and subway proximity, not GTFS timetables or service frequency.",
            "Walk and bike scores include local road-network nearest-amenity access, but they are still not full polygonal isochrones from a routing API.",
            "Transit and car scores remain neighborhood accessibility proxies rather than exact per-cell 15-minute path searches.",
        ],
        "mode_score_fields": {
            "baseline": [f"score_baseline_{mode}" for mode in ["walk", "bike", "transit", "car"]],
            "track": [f"score_track_{mode}" for mode in ["walk", "bike", "transit", "car"]],
            "composite": [f"score_composite_{mode}" for mode in ["walk", "bike", "transit", "car"]],
            "proxy_access": [f"proxy_access_{mode}" for mode in ["walk", "bike", "transit", "car"]],
            "network_access": ["network_access_walk", "network_access_bike", "network_track_access_walk", "network_track_access_bike"],
            "environment": ["ndvi", "ndvi_norm", "european_aqi", "aqi_norm"],
        },
        "ranges": {
            "price_min": float(h3_df["avg_price_m2"].min()),
            "price_max": float(h3_df["avg_price_m2"].max()),
            "distance_min": float(h3_df["avg_subway_distance_m"].min()),
            "distance_max": float(h3_df["avg_subway_distance_m"].max()),
        },
        "created_from_workspace": str(WORKSPACE_ROOT),
    }


def build_app_payload(feature_collection: dict) -> list[dict]:
    keep_props = [
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
    features = []
    integer_like = {
        "apartment_count",
        "school_count",
        "healthcare_count",
        "grocery_count",
        "park_count",
        "bus_stop_count",
        "subway_exit_count",
        "gym_count",
        "grid_cell_count",
    }
    one_decimal = {
        "avg_price_m2",
        "avg_subway_distance_m",
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
        "european_aqi",
    }
    three_decimal = {
        "ndvi",
        "ndvi_norm",
        "aqi_norm",
        "price_affordability_norm",
        "transit_norm",
        "park_norm",
        "bike_length_km",
    }

    def compact_value(key: str, value):
        if value is None:
            return None
        if isinstance(value, (np.integer, int)):
            return int(value)
        if isinstance(value, (np.floating, float)):
            if not np.isfinite(value):
                return None
            if key in integer_like:
                return int(round(value))
            if key in one_decimal:
                return round(float(value), 1)
            if key in three_decimal:
                return round(float(value), 3)
            return round(float(value), 4)
        return value

    for feature in feature_collection["features"]:
        coords = feature["geometry"]["coordinates"][0]
        simplified = [[round(float(lng), 5), round(float(lat), 5)] for lng, lat in (coords[:-1] if len(coords) > 1 else coords)]
        props = feature["properties"]
        features.append([simplified, [compact_value(key, props.get(key)) for key in keep_props]])
    return {"schema": keep_props, "features": features}


def main() -> None:
    ensure_dirs()
    boundary = load_boundary()

    print("Building 500m grid…")
    grid = build_grid(boundary)

    print("Scoring H3 support layers…")
    apartments = load_apartment_hex_stats()
    poi = build_poi_2024_hex_counts(boundary)
    roads = build_road_hex_metrics(boundary)
    h3_scored = score_h3_hexes(apartments, poi, roads)

    print("Attaching H3 support metrics to grid…")
    grid_scored = attach_hex_metrics_to_grid(grid, h3_scored)
    print("Attaching NDVI and AQI layers…")
    grid_scored = attach_environment_layers(grid_scored)

    print("Attaching walk/bike road-network accessibility…")
    network_access = build_network_accessibility_grid(grid_scored, boundary)
    grid_scored = grid_scored.merge(network_access, on="grid_id", how="left")

    print("Computing 15-minute grid accessibility proxies…")
    grid_scored = build_isochrone_proxy_scores(grid_scored)

    print("Aggregating grid back to H3…")
    h3_from_grid = aggregate_grid_to_h3(grid_scored)
    h3_from_grid = h3_from_grid.sort_values("score_composite_walk", ascending=False).reset_index(drop=True)

    grid_fc = build_grid_feature_collection(grid_scored)
    h3_fc = build_h3_feature_collection(h3_from_grid)
    manifest = build_manifest(grid_scored, h3_from_grid)

    GRID_GEOJSON.write_text(json.dumps(grid_fc, ensure_ascii=False), encoding="utf-8")
    GRID_JSON.write_text(grid_scored.to_json(orient="records", force_ascii=False), encoding="utf-8")
    SEED_GEOJSON.write_text(json.dumps(h3_fc, ensure_ascii=False), encoding="utf-8")
    SEED_JSON.write_text(h3_from_grid.to_json(orient="records", force_ascii=False), encoding="utf-8")
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    APP_MANIFEST.write_text(MANIFEST_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    APP_JSON.write_text(json.dumps(build_app_payload(h3_fc), ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "grid_json": str(GRID_JSON),
                "grid_geojson": str(GRID_GEOJSON),
                "seed_geojson": str(SEED_GEOJSON),
                "manifest": str(MANIFEST_JSON),
                "grid_cell_count": int(len(grid_scored)),
                "feature_count": int(len(h3_from_grid)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
