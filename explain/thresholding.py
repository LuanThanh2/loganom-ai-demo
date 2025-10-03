from typing import Tuple

import numpy as np
import pandas as pd

from models.utils import load_models_config


def compute_threshold(scores: pd.Series) -> Tuple[float, int]:
    cfg = load_models_config()
    method = cfg.get("scoring", {}).get("threshold_method", "quantile")
    contamination = cfg.get("isolation_forest", {}).get("contamination", 0.05)
    if method == "quantile":
        thr = np.quantile(scores, 1.0 - contamination)
        count = int((scores >= thr).sum())
        return float(thr), count
    # default fallback
    thr = float(scores.mean() + scores.std())
    count = int((scores >= thr).sum())
    return thr, count
