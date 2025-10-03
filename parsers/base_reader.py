import json
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from models.utils import ensure_dir


def read_jsonl(path: Path) -> List[Dict]:
    items: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed JSON line
                # For demo robustness, we ignore bad lines instead of failing hard
                continue
    return items


def to_utc_datetime(series: Iterable) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def write_partitioned_parquet(df: pd.DataFrame, base_out: Path, source_name: str) -> None:
    if df.empty:
        return
    df = df.copy()
    df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
    df["dt"] = df["@timestamp"].dt.strftime("%Y-%m-%d")
    for dt_value, part in df.groupby("dt"):
        out_dir = base_out / source_name / f"dt={dt_value}"
        ensure_dir(out_dir)
        out_path = out_dir / "part.parquet"
        part.drop(columns=["dt"], inplace=True)
        part.to_parquet(out_path, index=False)
