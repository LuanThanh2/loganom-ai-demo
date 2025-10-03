from pathlib import Path
from typing import List

import pandas as pd

from models.utils import get_paths, ensure_dir
from features.windowing import add_time_window_counts
from features.entropy import shannon_entropy
from features.sessionize import sessionize_network


SOURCES = ["windows_evtx", "sysmon", "zeek_conn", "syslog_auth"]


def load_ecs_sources() -> pd.DataFrame:
    paths = get_paths()
    base = Path(paths["ecs_parquet_dir"]).resolve()
    frames: List[pd.DataFrame] = []
    for src in SOURCES:
        for part in (base / src).rglob("*.parquet"):
            frames.append(pd.read_parquet(part))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
    return df


def build_feature_table() -> Path:
    paths = get_paths()
    out_dir = Path(paths["features_dir"]).resolve()
    ensure_dir(out_dir)

    ecs = load_ecs_sources()
    if ecs.empty:
        out_path = out_dir / "features.parquet"
        pd.DataFrame().to_parquet(out_path, index=False)
        return out_path

    ecs = ecs.sort_values("@timestamp")

    # Ensure expected columns exist
    for col in ["event.code", "event.outcome", "destination.port", "process.command_line", "host.name", "user.name", "source.ip", "destination.ip"]:
        if col not in ecs.columns:
            ecs[col] = None

    # Derive simple flags for windows
    ecs["login_failed"] = ((ecs["event.code"].astype(str) == "4625") | (ecs["event.outcome"] == "Failure")).fillna(False).astype(int)
    ecs["conn_suspicious"] = ((ecs["destination.port"].astype(float) == 4444.0) | (ecs["event.outcome"] == "S0")).fillna(False).astype(int)

    # Entropy for command line
    ecs["process.command_line_entropy"] = ecs["process.command_line"].astype(str).apply(shannon_entropy)

    # Sessionize network
    ecs = sessionize_network(ecs)

    # Window features grouped by host and user
    for flag in ["login_failed", "conn_suspicious"]:
        ecs = add_time_window_counts(ecs, ["host.name"], "@timestamp", flag, [1, 5, 15])
        ecs = add_time_window_counts(ecs, ["user.name"], "@timestamp", flag, [1, 5, 15])

    # Final feature columns
    feature_cols = [
        "login_failed", "conn_suspicious", "process.command_line_entropy",
    ]
    for w in [1, 5, 15]:
        for ent in ["login_failed", "conn_suspicious"]:
            feature_cols += [f"{ent}_count_{w}m", f"{ent}_rate_{w}m"]

    # Keep identity columns
    id_cols = ["@timestamp", "host.name", "user.name", "source.ip", "destination.ip", "session.id"]
    for col in id_cols:
        if col not in ecs.columns:
            ecs[col] = None

    feat = ecs[id_cols + feature_cols].copy()
    out_path = out_dir / "features.parquet"
    feat.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    build_feature_table()
