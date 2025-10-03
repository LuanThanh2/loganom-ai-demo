from pathlib import Path
from typing import List, Dict

import pandas as pd

from models.utils import get_paths, load_yaml
from parsers.base_reader import read_jsonl, write_partitioned_parquet
from parsers.ecs_mapper import map_record


def parse_zeek_conn() -> Path:
    paths = get_paths()
    raw = Path(paths["raw_data_dir"]) / "zeek_conn.jsonl"
    ecs_parquet_dir = Path(paths["ecs_parquet_dir"]).resolve()

    mapping = load_yaml(Path(__file__).resolve().parents[1] / "config" / "ecs_mapping.yaml")
    cfg = mapping["zeek_conn"]

    records: List[Dict] = read_jsonl(raw)
    ecs_rows = [map_record(rec, cfg) for rec in records]
    df = pd.DataFrame(ecs_rows)
    df["event.module"] = "zeek"
    df["event.dataset"] = "zeek.conn"
    df = df.dropna(subset=["@timestamp"])  # ensure ts present
    write_partitioned_parquet(df, Path(paths["ecs_parquet_dir"]), "zeek_conn")
    return ecs_parquet_dir


if __name__ == "__main__":
    parse_zeek_conn()
