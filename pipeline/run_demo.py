"""Orchestrator (Tiếng Việt)

Chạy toàn bộ pipeline demo theo thứ tự:
1) ingest: đọc dữ liệu mẫu, chuẩn hóa ECS, ghi Parquet phân vùng theo ngày
2) featurize: xây dựng đặc trưng (cửa sổ thời gian, entropy, session)
3) train: huấn luyện Isolation Forest và lưu model
4) score: sinh điểm bất thường và lưu Parquet
5) alert + bundle: chọn top alerts theo threshold và tạo Forensic Bundles
"""

from pathlib import Path

from pipeline.ingest import ingest_all
from features.build_features import build_feature_table
from models.train_if import train_model
from models.infer import score_features
from pipeline.alerting import select_alerts
from pipeline.bundle import build_bundles_for_top_alerts
from models.utils import get_paths


def run_all() -> Path:
    ingest_all()
    build_feature_table()
    train_model()
    scores_path = score_features()
    top, thr = select_alerts(str(scores_path))
    build_bundles_for_top_alerts(top, thr)
    return Path(get_paths()["bundles_dir"])  


if __name__ == "__main__":
    run_all()
