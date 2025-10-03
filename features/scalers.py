from typing import List, Tuple

import pandas as pd
from sklearn.preprocessing import RobustScaler


def fit_transform_robust(df: pd.DataFrame, feature_cols: List[str]) -> Tuple[pd.DataFrame, RobustScaler]:
    scaler = RobustScaler()
    X = df[feature_cols].fillna(0.0).values
    Xs = scaler.fit_transform(X)
    out = df.copy()
    out[feature_cols] = Xs
    return out, scaler


def transform_robust(df: pd.DataFrame, feature_cols: List[str], scaler: RobustScaler) -> pd.DataFrame:
    X = df[feature_cols].fillna(0.0).values
    Xs = scaler.transform(X)
    out = df.copy()
    out[feature_cols] = Xs
    return out
