"""Score ensembling between Isolation Forest and LSTM AE.

Produces data/scores/ensemble_scores.parquet with column ensemble.score.
"""

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

    if_df = pd.read_parquet(if_scores_path)
    lstm_df = pd.read_parquet(lstm_scores_path)

    # Align by timestamp (best-effort)
    for d in (if_df, lstm_df):
        if "@timestamp" in d.columns:
            d["@timestamp"] = pd.to_datetime(d["@timestamp"], utc=True, errors="coerce")

    merged = pd.merge_asof(
        if_df.sort_values("@timestamp"),
        lstm_df.sort_values("@timestamp")[["@timestamp", "lstm.mse"]],
        on="@timestamp",
        direction="nearest",
        tolerance=pd.Timedelta("1m"),
    )

    if_score = merged["anom.score"].astype(float).values
    lstm_score = merged["lstm.mse"].astype(float).fillna(0.0).values

    if_n = _minmax(if_score)
    lstm_n = _minmax(lstm_score)

    # As referenced: ensemble_score = 0.5*(1 - if_score) + 0.5*lstm_score (normalized)
    ensemble = w_if * (1.0 - if_n) + w_lstm * lstm_n
    out = merged.copy()
    out["ensemble.score"] = ensemble

    out_path = scores_root / "ensemble_scores.parquet"
    out.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    combine_if_lstm()


