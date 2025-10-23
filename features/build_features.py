from pathlib import Path
from typing import List, Tuple
import pandas as pd

from models.utils import get_paths, ensure_dir
from features.windowing import add_time_window_counts
from features.entropy import shannon_entropy
from features.sessionize import sessionize_network

def _list_sources(ecs_root: Path) -> List[str]:
    if not ecs_root.exists():
        return []
    return sorted([p.name for p in ecs_root.iterdir() if p.is_dir()])

def _available_dates(ecs_root: Path, sources: List[str]) -> List[str]:
    dts = set()
    for s in sources:
        base = ecs_root / s
        if not base.exists():
            continue
        for p in base.glob("dt=*"):
            if p.is_dir():
                dts.add(p.name.split("=", 1)[1])
    return sorted(dts)

def _read_partition(ecs_root: Path, dt: str, sources: List[str]) -> pd.DataFrame:
    parts = []
    for s in sources:
        parts.extend((ecs_root / s / f"dt={dt}").glob("*.parquet"))
    if not parts:
        return pd.DataFrame()
    frames = []
    for p in parts:
        try:
            frames.append(pd.read_parquet(p))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

def build_feature_table_large(sample_per_day: int = 100_000) -> Path:
    """
    Xây features theo từng ngày (partition) để tiết kiệm RAM; xuất gộp features.parquet nhỏ.
    """
    paths = get_paths()
    ecs_root = Path(paths["ecs_parquet_dir"]).resolve()
    feat_root = Path(paths["features_dir"]).resolve()
    ensure_dir(feat_root)

    sources = _list_sources(ecs_root)
    dates = _available_dates(ecs_root, sources)

    samples = []
    for dt in dates:
        ecs = _read_partition(ecs_root, dt, sources)
        if ecs.empty:
            continue

        # Chuẩn hoá thời gian
        if "@timestamp" in ecs.columns:
            ecs["@timestamp"] = pd.to_datetime(ecs["@timestamp"], utc=True, errors="coerce")
            ecs = ecs.dropna(subset=["@timestamp"]).sort_values("@timestamp")
        else:
            # Không có timestamp thì bỏ qua ngày này
            continue

        # Bổ sung cột thiếu
        for col in [
            "event.code", "event.outcome", "destination.port",
            "process.command_line", "host.name", "user.name",
            "source.ip", "destination.ip"
        ]:
            if col not in ecs.columns:
                ecs[col] = None

        # Cờ sự kiện
        ecs["login_failed"] = (
            (ecs["event.code"].astype(str) == "4625") |
            (ecs["event.outcome"].astype(str).str.lower() == "failure")
        ).fillna(False).astype(int)

        ecs["conn_suspicious"] = (
            (pd.to_numeric(ecs["destination.port"], errors="coerce") == 4444) |
            (ecs["event.outcome"].astype(str) == "S0")
        ).fillna(False).astype(int)

        # Entropy lệnh
        ecs["process.command_line_entropy"] = ecs["process.command_line"].astype(str).apply(shannon_entropy)

        # Sessionize (an toàn với try)
        try:
            ecs = sessionize_network(ecs)
        except Exception:
            if "session.id" not in ecs.columns:
                ecs["session.id"] = None

        # Rolling counts theo host và user cho 2 cờ
        for flag in ["login_failed", "conn_suspicious"]:
            ecs = add_time_window_counts(ecs, ["host.name"], "@timestamp", flag, [1, 5, 15])
            ecs = add_time_window_counts(ecs, ["user.name"], "@timestamp", flag, [1, 5, 15])

        # Chọn cột features đúng tên
        feature_cols = [
            "login_failed",
            "conn_suspicious",
            "process.command_line_entropy",
        ]
        for w in [1, 5, 15]:
            for flag in ["login_failed", "conn_suspicious"]:
                col = f"{flag}_count_{w}m"
                if col in ecs.columns:
                    feature_cols.append(col)

        # ID columns
        id_cols = ["@timestamp", "host.name", "user.name", "source.ip", "destination.ip", "session.id"]
        for c in id_cols:
            if c not in ecs.columns:
                ecs[c] = None

        feat = ecs[id_cols + feature_cols].copy()

        # Ghi per-partition
        out_dir = feat_root / f"dt={dt}"
        ensure_dir(out_dir)
        out_path = out_dir / "part.parquet"
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        feat.to_parquet(out_path, index=False)

        # Lấy mẫu để ghép ra features.parquet
        if sample_per_day > 0 and len(feat) > 0:
            k = min(sample_per_day, len(feat))
            samples.append(feat.sample(k, random_state=42))

    # Ghi bản gộp nhỏ
    out_all = feat_root / "features.parquet"
    if samples:
        pd.concat(samples, ignore_index=True).to_parquet(out_all, index=False)
    else:
        pd.DataFrame(columns=["@timestamp"]).to_parquet(out_all, index=False)
    return out_all

def build_feature_table() -> Path:
    """Wrapper để CLI gọi; mặc định dùng large-mode."""
    return build_feature_table_large()