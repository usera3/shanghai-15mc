from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
GRID_JSON = PROCESSED_DIR / "shanghai_grid_seed.json"
OUT_JSON = PROCESSED_DIR / "shanghai_environment_layers.json"
STAC_URL = "https://earth-search.aws.element84.com/v1/search"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def load_grid() -> pd.DataFrame:
    return pd.read_json(GRID_JSON)


def fetch_aqi(grid: pd.DataFrame) -> pd.DataFrame:
    # Use a coarse sample to limit API payload while still producing a spatial surface.
    coarse = grid.copy()
    coarse["aqi_lon_round"] = coarse["center_lon"].round(1)
    coarse["aqi_lat_round"] = coarse["center_lat"].round(1)
    coarse = coarse[["aqi_lon_round", "aqi_lat_round"]].drop_duplicates().reset_index(drop=True)

    rows = []
    batch_size = 12
    for start in range(0, len(coarse), batch_size):
        batch = coarse.iloc[start : start + batch_size]
        latitudes = ",".join(batch["aqi_lat_round"].astype(str).tolist())
        longitudes = ",".join(batch["aqi_lon_round"].astype(str).tolist())
        params = {
            "latitude": latitudes,
            "longitude": longitudes,
            "current": "european_aqi,pm2_5,pm10,nitrogen_dioxide,ozone",
            "timezone": "Asia/Shanghai",
            "domains": "cams_global",
        }
        response = requests.get(AQI_URL, params=params, timeout=180)
        response.raise_for_status()
        data = response.json()
        payloads = [data] if isinstance(data, dict) else data

        for payload in payloads:
            current = payload.get("current", {})
            rows.append(
                {
                    "aqi_lon_round": round(float(payload["longitude"]), 2),
                    "aqi_lat_round": round(float(payload["latitude"]), 2),
                    "european_aqi": current.get("european_aqi"),
                    "pm2_5": current.get("pm2_5"),
                    "pm10": current.get("pm10"),
                    "nitrogen_dioxide": current.get("nitrogen_dioxide"),
                    "ozone": current.get("ozone"),
                }
            )
    return pd.DataFrame(rows).drop_duplicates(subset=["aqi_lon_round", "aqi_lat_round"])


def fetch_best_sentinel_item(grid: pd.DataFrame) -> dict:
    bbox = [
        float(grid["center_lon"].min()),
        float(grid["center_lat"].min()),
        float(grid["center_lon"].max()),
        float(grid["center_lat"].max()),
    ]
    payload = {
        "collections": ["sentinel-2-c1-l2a"],
        "bbox": bbox,
        "datetime": "2025-05-01T00:00:00Z/2025-10-31T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 10}},
        "limit": 40,
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    data = requests.post(STAC_URL, json=payload, timeout=180).json()
    return data["features"]


def sample_ndvi(grid: pd.DataFrame, items: list[dict]) -> pd.DataFrame:
    sample = grid.iloc[::15].copy().reset_index(drop=True)
    sample["ndvi"] = np.nan

    tile_geoms = []
    for item in items:
        try:
            geom = shape(item["geometry"])
            tile_geoms.append((item, geom))
        except Exception:
            continue

    for item, geom in tile_geoms:
        mask = contains_xy(geom, sample["center_lon"].to_numpy(), sample["center_lat"].to_numpy())
        idx = np.where(mask & sample["ndvi"].isna().to_numpy())[0]
        if len(idx) == 0:
            continue

        red_url = item["assets"]["red"]["href"]
        nir_url = item["assets"]["nir"]["href"]
        lon_vals = sample.loc[idx, "center_lon"].to_numpy()
        lat_vals = sample.loc[idx, "center_lat"].to_numpy()

        with rasterio.open(red_url) as red_ds, rasterio.open(nir_url) as nir_ds:
            transformer = Transformer.from_crs("EPSG:4326", red_ds.crs, always_xy=True)
            xs, ys = transformer.transform(lon_vals.tolist(), lat_vals.tolist())
            coords = list(zip(xs, ys))
            red_vals = [val[0] for val in red_ds.sample(coords)]
            nir_vals = [val[0] for val in nir_ds.sample(coords)]

        red = pd.to_numeric(pd.Series(red_vals), errors="coerce").replace(0, np.nan) * 0.0001
        nir = pd.to_numeric(pd.Series(nir_vals), errors="coerce").replace(0, np.nan) * 0.0001
        ndvi = (nir - red) / (nir + red)
        sample.loc[idx, "ndvi"] = ndvi.to_numpy()

    sample["ndvi"] = sample["ndvi"].fillna(sample["ndvi"].median())
    sample["ndvi_lon_round"] = sample["center_lon"].round(2)
    sample["ndvi_lat_round"] = sample["center_lat"].round(2)
    out = (
        sample.groupby(["ndvi_lon_round", "ndvi_lat_round"], as_index=False)
        .agg(ndvi=("ndvi", "mean"))
    )
    return out


def main() -> None:
    grid = load_grid()
    aqi = fetch_aqi(grid)
    sentinel_items = fetch_best_sentinel_item(grid)
    ndvi = sample_ndvi(grid, sentinel_items)

    result = {
        "aqi": aqi.to_dict(orient="records"),
        "ndvi": ndvi.to_dict(orient="records"),
        "sentinel_item_id": sentinel_items[0]["id"] if sentinel_items else None,
        "sentinel_cloud_cover": sentinel_items[0]["properties"].get("eo:cloud_cover") if sentinel_items else None,
        "sentinel_item_count": len(sentinel_items),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT_JSON), "sentinel_item_count": len(sentinel_items)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
