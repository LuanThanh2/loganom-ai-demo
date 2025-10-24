"""Inference for LSTM Autoencoder anomaly scores.

Writes data/scores/lstm_scores.parquet with columns:
- original feature columns + lstm.mse (float) and lstm.anomaly (bool)
"""

from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd

from models.utils import get_paths


def _load_lstm_payload() -> Dict:
    paths = get_paths()
    p = Path(paths["models_dir"]) / "lstm_anomaly.joblib"
    if not p.exists():
        raise FileNotFoundError(f"LSTM model not found: {p}")
    return joblib.load(p)


def score_lstm_features() -> Path:
    paths = get_paths()
    payload = _load_lstm_payload()
    model = payload["model"]
    meta = payload.get("meta", {})
    feature_cols: List[str] = payload.get("feature_cols", [])

    feat_path = Path(paths["features_dir"]) / "features.parquet"
    df = pd.read_parquet(feat_path)
    if df.empty:
        raise RuntimeError("Feature table is empty")

    if "@timestamp" in df.columns:
        df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["@timestamp"]).sort_values("@timestamp")

    # Ensure feature columns exist
    for c in feature_cols:
        if c not in df.columns:
            df[c] = 0.0
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).values

    mse = model.reconstruction_mse(X)
    seq_len = int(meta.get("sequence_length", 60))

    out = df.copy()
    out["lstm.mse"] = np.nan
    out["lstm.anomaly"] = False
    if len(mse) > 0:
        out.loc[seq_len - 1 : seq_len - 1 + len(mse) - 1, "lstm.mse"] = mse

    # Threshold: quantile 95% of available MSEs
    if np.isfinite(out["lstm.mse"]).any():
        valid = out["lstm.mse"].dropna().values
        thr = float(np.quantile(valid, 0.95)) if len(valid) > 0 else float("inf")
        out["lstm.anomaly"] = out["lstm.mse"] >= thr

    out_dir = Path(paths["scores_dir"]) ; out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "lstm_scores.parquet"
    out.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    score_lstm_features()


