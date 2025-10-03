from datetime import timedelta
from typing import List

import pandas as pd


def sessionize_network(df: pd.DataFrame, ts_col: str = "@timestamp", timeout_seconds: int = 120) -> pd.DataFrame:
    # Create a naive session id by grouping by 4/5-tuple and breaking on inactivity
    df = df.copy()
    for col in ["source.ip", "source.port", "destination.ip", "destination.port", "network.transport"]:
        if col not in df.columns:
            df[col] = None
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.sort_values(["source.ip", "destination.ip", ts_col])
    session_id = []
    last_key = None
    last_time = None
    current_id = 0
    for row in df[["source.ip", "source.port", "destination.ip", "destination.port", "network.transport", ts_col]].itertuples(index=False):
        key = (row[0], row[2], row[4])  # src ip, dst ip, proto
        t = row[5]
        if key != last_key or last_time is None or (t - last_time).total_seconds() > timeout_seconds:
            current_id += 1
        session_id.append(current_id)
        last_key = key
        last_time = t
    df["session.id"] = session_id
    return df
