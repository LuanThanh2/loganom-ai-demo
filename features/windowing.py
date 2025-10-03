import pandas as pd
from typing import List


def add_time_window_counts(df: pd.DataFrame, group_keys: List[str], ts_col: str, flag_col: str, windows_min: List[int]) -> pd.DataFrame:
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")

    for key in group_keys:
        if key not in df.columns:
            df[key] = "unknown"

    for w in windows_min:
        win = f"{w}min"
        name = f"{flag_col}_count_{w}m"

        def _roll_group(g: pd.DataFrame) -> pd.Series:
            g = g.copy()
            g = g.dropna(subset=[ts_col])
            if g.empty:
                return pd.Series(index=g.index, dtype="float64")
            g_sorted = g.sort_values(ts_col)
            r = g_sorted.rolling(win, on=ts_col, min_periods=1)[flag_col].sum()
            # align back to original group index order
            r = r.reindex(g_sorted.index)
            return r.reindex(g.index)

        rolled = (
            df.groupby(group_keys, group_keys=False)
              .apply(_roll_group)
        )
        df[name] = rolled
        rate_name = f"{flag_col}_rate_{w}m"
        df[rate_name] = df[name] / (w * 60.0)

    return df
