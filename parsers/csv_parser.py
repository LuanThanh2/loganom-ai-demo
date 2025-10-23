from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional
from parsers.base_reader import ParquetBatchWriter
import pandas as pd
from models.utils import get_paths

def _norm_col(name: str) -> str:
    s = re.sub(r"\s+", "_", name.strip().lower())
    s = re.sub(r"[^0-9a-z0-9_]", "", s)
    return s

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: _norm_col(c) for c in df.columns})

def _pick_first(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c and c in df.columns:
            return c
    return None

def parse_csv_file(csv_path: Path, out_subdir: str = "custom_csv") -> None:
    paths = get_paths()
    out_root = Path(paths["ecs_parquet_dir"])
    writer = ParquetBatchWriter(out_root, out_subdir)
    CHUNK_ROWS = int(os.getenv("CHUNK_ROWS", "200000"))

    for df in pd.read_csv(csv_path, chunksize=CHUNK_ROWS, low_memory=False):
        if df.empty:
            continue
        df = _normalize_columns(df)
        env_time = os.getenv("CSV_TIME_COL")
        if env_time:
            env_time = _norm_col(env_time)
        time_candidates = [env_time, "timestamp","datetime","date_time","time","ts","flow_start","starttime","start_time"]
        time_candidates = [c for c in time_candidates if c]
        tcol = _pick_first(df, time_candidates)
        if not tcol:
            continue
        ts = pd.to_datetime(df[tcol], utc=True, errors="coerce", infer_datetime_format=True, dayfirst=True)
        df["@timestamp"] = ts
        df = df.dropna(subset=["@timestamp"])
        if df.empty:
            continue
        src_ip_col = _pick_first(df, ["src_ip","source_ip","ip_src","srcip","sourceaddress"])
        dst_ip_col = _pick_first(df, ["dst_ip","destination_ip","ip_dst","dstip","destinationaddress"])
        if src_ip_col: df["source.ip"] = df[src_ip_col]
        if dst_ip_col: df["destination.ip"] = df[dst_ip_col]
        src_port_col = _pick_first(df, ["src_port","sport","source_port"])
        dst_port_col = _pick_first(df, ["dst_port","dport","destination_port"])
        if src_port_col: df["source.port"] = pd.to_numeric(df[src_port_col], errors="coerce").astype("Int64")
        if dst_port_col: df["destination.port"] = pd.to_numeric(df[dst_port_col], errors="coerce").astype("Int64")
        proto_col = _pick_first(df, ["protocol","proto"])
        if proto_col: df["network.transport"] = df[proto_col].astype(str).str.lower()
        label_col = _pick_first(df, ["label","attack_cat","attack_category"])
        df["event.action"] = df[label_col].astype(str) if label_col else "flow"
        host_col = _pick_first(df, ["host","hostname"])
        user_col = _pick_first(df, ["user","username","account"])
        if host_col: df["host.name"] = df[host_col]
        if user_col: df["user.name"] = df[user_col]
        fwd_bytes = _pick_first(df, ["tot_fwd_bytes","total_fwd_bytes"])
        bwd_bytes = _pick_first(df, ["tot_bwd_bytes","total_bwd_bytes"])
        if fwd_bytes and bwd_bytes:
            df["network.bytes"] = pd.to_numeric(df[fwd_bytes], errors="coerce").fillna(0) + pd.to_numeric(df[bwd_bytes], errors="coerce").fillna(0)

        df["event.dataset"] = "custom_csv"
        df["dt"] = pd.to_datetime(df["@timestamp"], utc=True).dt.strftime("%Y-%m-%d")
        keep_cols = [
            "@timestamp","event.dataset","event.action","host.name","user.name",
            "source.ip","source.port","destination.ip","destination.port",
            "network.transport","network.bytes","dt"
        ]
        cols = [c for c in keep_cols if c in df.columns]
        writer.write(df[cols])
        
def parse_custom_csv_dir(in_dir: Path, recursive: bool = True) -> None:
    files = list(in_dir.rglob("*.csv")) if recursive else list(in_dir.glob("*.csv"))
    for p in files:
        try:
            parse_csv_file(p)
        except Exception as e:
            print(f"[csv] skip {p}: {e}")