import sys
from pathlib import Path

# Ensure project root is on sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from pathlib import Path

from models.utils import get_paths

st.title("Hosts")
paths = get_paths()

scores_path = Path(paths["scores_dir"]) / "scores.parquet"
if not scores_path.exists():
    st.warning("Scores not found. Run the demo pipeline first.")
else:
    df = pd.read_parquet(scores_path)
    hosts = sorted([h for h in df["host.name"].dropna().unique() if h])
    host = st.selectbox("Select host", hosts or ["(none)"])

    if hosts:
        dff = df[df["host.name"] == host].sort_values("@timestamp")
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(pd.to_datetime(dff["@timestamp"]), dff["anom.score"], marker='o', linestyle='-')
        ax.set_title(f"Anomaly Scores for {host}")
        ax.set_ylabel("Score")
        ax.set_xlabel("Time")
        st.pyplot(fig)

        st.dataframe(dff[["@timestamp", "user.name", "source.ip", "destination.ip", "anom.score"]].tail(50))
