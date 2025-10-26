"""Score ensembling between Isolation Forest and LSTM AE.

Produces data/scores/ensemble_scores.parquet with column ensemble.score.
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd

from models.utils import get_paths


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = np.min(x), np.max(x)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo == 0:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def combine_if_lstm(if_scores_path: Path = None, lstm_scores_path: Path = None, w_if: float = 0.5, w_lstm: float = 0.5) -> Path:
    paths = get_paths()
    scores_root = Path(paths["scores_dir"]) ; scores_root.mkdir(parents=True, exist_ok=True)
    if if_scores_path is None:
        if_scores_path = scores_root / "scores.parquet"
    if lstm_scores_path is None:
        lstm_scores_path = scores_root / "lstm_scores.parquet"

    # Read only required columns for efficiency
    if_df = pd.read_parquet(if_scores_path, columns=["@timestamp", "anom.score"])  # type: ignore[arg-type]
    lstm_df = pd.read_parquet(lstm_scores_path, columns=["@timestamp", "lstm.mse"])  # type: ignore[arg-type]

    # Optional downsampling to "fake" ensemble on a small subset
    try:
        sample_frac = float(os.getenv("ENSEMBLE_SAMPLE_FRAC", "0"))
    except Exception:
        sample_frac = 0.0
    try:
        max_rows = int(os.getenv("ENSEMBLE_MAX_ROWS", "0"))
    except Exception:
        max_rows = 0

    for name, d in ("if", if_df), ("lstm", lstm_df):
        if sample_frac > 0 and sample_frac < 1 and len(d) > 0:
            d = d.sample(frac=sample_frac, random_state=42)
        elif max_rows > 0 and len(d) > max_rows:
            d = d.sample(n=max_rows, random_state=42)
        # Assign back after sampling
        if name == "if":
            if_df = d
        else:
            lstm_df = d

    # Align by timestamp (best-effort)
    for d in (if_df, lstm_df):
        if "@timestamp" in d.columns:
            d["@timestamp"] = pd.to_datetime(d["@timestamp"], utc=True, errors="coerce")

    tol_str = os.getenv("ENSEMBLE_TIME_TOLERANCE", "1m")
    merged = pd.merge_asof(
        if_df.sort_values("@timestamp"),
        lstm_df.sort_values("@timestamp")[["@timestamp", "lstm.mse"]],
        on="@timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(tol_str),
    )

    if_score = merged["anom.score"].astype(float).values
    lstm_score = merged["lstm.mse"].astype(float).fillna(0.0).values

    if_n = _minmax(if_score)
    lstm_n = _minmax(lstm_score)

    # Optional weight overrides via ENV; keep default formula as-is
    try:
        w_if_env = float(os.getenv("ENSEMBLE_W_IF", str(w_if)))
    except Exception:
        w_if_env = w_if
    try:
        w_lstm_env = float(os.getenv("ENSEMBLE_W_LSTM", str(w_lstm)))
    except Exception:
        w_lstm_env = w_lstm

    ensemble = w_if_env * (1.0 - if_n) + w_lstm_env * lstm_n
    out = merged.copy()
    out["ensemble.score"] = ensemble

    out_path = scores_root / "ensemble_scores.parquet"
    out.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    combine_if_lstm()


