"""Suy luận/Chấm điểm bất thường (Tiếng Việt)

- Tải payload model (model, scaler, feature_cols)
- Biến đổi đặc trưng bằng scaler, tính `anom.score = -decision_function`
- Lưu vào `data/scores/scores.parquet`
"""

from pathlib import Path
from typing import Dict

import joblib
import pandas as pd

from models.utils import get_paths


def score_features() -> Path:
    paths = get_paths()
    feat_path = Path(paths["features_dir"]) / "features.parquet"
    model_path = Path(paths["models_dir"]) / "isolation_forest.joblib"

    df = pd.read_parquet(feat_path)
    if df.empty:
        raise RuntimeError("Feature table is empty; run featurize first")

    payload: Dict = joblib.load(model_path)
    model = payload["model"]
    feature_cols = payload["feature_cols"]
    scaler = payload.get("scaler")

    X = df[feature_cols].fillna(0.0)
    X_in = scaler.transform(X) if scaler is not None else X.values

    # sklearn's decision_function: larger is less abnormal; negative is more abnormal
    scores = -model.decision_function(X_in)

    out = df.copy()
    out["anom.score"] = scores

    out_dir = Path(paths["scores_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "scores.parquet"
    out.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    score_features()
