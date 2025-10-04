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
from pathlib import Path
from datetime import datetime

from models.utils import get_paths

st.title("Overview")

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
    st.metric("Events processed", len(df))

    fig, ax = plt.subplots(figsize=(10, 3))
    df_sorted = df.sort_values("@timestamp")
    ax.plot(pd.to_datetime(df_sorted["@timestamp"]), df_sorted["anom.score"], marker='o', linestyle='-')
    ax.set_title("Anomaly Score Timeline")
    ax.set_ylabel("Score")
    ax.set_xlabel("Time")
    st.pyplot(fig)
