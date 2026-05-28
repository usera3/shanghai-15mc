from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_2024 = ROOT / "data" / "raw" / "poi_2024" / "POI 2024" / "csv格式" / "已分类"
OUT_JSON = ROOT / "data" / "processed" / "poi_2024_probe.json"


FILES = {
    "transport": "上海市-1754933-utf8.csv-交通设施服务.csv",
    "sport": "上海市-1754933-utf8.csv-体育休闲服务.csv",
    "health": "上海市-1754933-utf8.csv-医疗保健服务.csv",
    "education": "上海市-1754933-utf8.csv-科教文化服务.csv",
    "shopping": "上海市-1754933-utf8.csv-购物服务.csv",
    "parks": "上海市-1754933-utf8.csv-风景名胜.csv",
}


def summarize_file(path: Path) -> dict:
    df = pd.read_csv(path, nrows=50_000)
    out = {
        "rows_sampled": int(len(df)),
        "midType_top": df["midType"].fillna("NA").value_counts().head(15).to_dict(),
        "smallType_top": df["smallType"].fillna("NA").value_counts().head(15).to_dict(),
    }
    return out


def build_probe() -> dict:
    probe = {"base_dir": str(RAW_2024), "files": {}}
    for key, filename in FILES.items():
        path = RAW_2024 / filename
        probe["files"][key] = {
            "path": str(path),
            "exists": path.exists(),
            "size_mb": round(path.stat().st_size / 1_048_576, 2) if path.exists() else None,
            "summary": summarize_file(path) if path.exists() else None,
        }
    return probe


def main() -> None:
    probe = build_probe()
    OUT_JSON.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"probe": str(OUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
