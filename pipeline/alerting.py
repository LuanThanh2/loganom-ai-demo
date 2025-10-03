from typing import Tuple

import pandas as pd

from explain.thresholding import compute_threshold
from models.utils import load_models_config


def select_alerts(scores_path: str) -> Tuple[pd.DataFrame, float]:
    cfg = load_models_config()
    top_n = cfg.get("scoring", {}).get("top_n", 10)

    df = pd.read_parquet(scores_path)
    thr, _ = compute_threshold(df["anom.score"]) 
    high = df[df["anom.score"] >= thr].copy()
    high = high.sort_values("anom.score", ascending=False).head(top_n)
    return high, thr
