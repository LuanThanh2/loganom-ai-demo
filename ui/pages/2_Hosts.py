import sys
from pathlib import Path

# Ensure project root is on sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime

from models.utils import get_paths

st.title("Hosts")
paths = get_paths()

scores_path = Path(paths["scores_dir"]) / "scores.parquet"
colA, colB = st.columns(2)
with colA:
    if st.button("Reload data"):
        st.experimental_rerun()
with colB:
    if scores_path.exists():
        mtime = datetime.fromtimestamp(os.path.getmtime(scores_path)).strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"scores.parquet last modified: {mtime}")

if not scores_path.exists():
    st.warning("Scores not found. Run the demo pipeline first.")
else:
    df = pd.read_parquet(scores_path)
    # NEW: chuẩn hóa thời gian + điền host/user rỗng = "unknown"
    df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
    df["host.name"] = df.get("host.name").fillna("unknown")
    df["user.name"] = df.get("user.name").fillna("unknown")

    hosts = sorted(df["host.name"].unique().tolist())
    host = st.selectbox("Select host", hosts or ["unknown"])

    if hosts:
        dff = df[df["host.name"] == host].sort_values("@timestamp")
        if not dff.empty:
            fig, ax = plt.subplots(figsize=(10, 3))
            ax.plot(pd.to_datetime(dff["@timestamp"]), dff["anom.score"], marker='o', linestyle='-')
            ax.set_title(f"Anomaly Scores for {host}")
            ax.set_ylabel("Score")
            ax.set_xlabel("Time")
            st.pyplot(fig)

            st.dataframe(
                dff[["@timestamp", "user.name", "source.ip", "destination.ip", "anom.score"]].tail(200)
            )
        else:
            st.info("No rows for selected host.")