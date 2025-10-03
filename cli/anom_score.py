from __future__ import annotations

import os
from pathlib import Path

from models.utils import get_paths
from pipeline.build_store import run_ingest

try:
    from parsers.csv_parser import parse_csv_file  # type: ignore
except Exception:
    parse_csv_file = None  # type: ignore

try:
    from parsers.syslog_parser import parse_auth_logs  # type: ignore
except Exception:
    parse_auth_logs = None  # type: ignore

def _ingest_csv_recursive(root: Path) -> None:
    if parse_csv_file is None:
        print("[ingest] CSV parser not available, skip CSV ingest.")
        return
    if not root.exists():
        print(f"[ingest] CSV root not found: {root}")
        return
    files = list(root.rglob("*.csv"))
    if not files:
        print(f"[ingest] No CSV files under: {root}")
        return
    print(f"[ingest] Found {len(files)} CSV file(s)")
    for p in files:
        try:
            parse_csv_file(p)
            print(f"[ingest] CSV ingested: {p}")
        except Exception as e:
            print(f"[ingest] CSV skipped {p}: {e}")

def ingest_all() -> Path:
    paths = get_paths()
    out_dir = Path(paths["ecs_parquet_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_ingest()
    except Exception as e:
        print(f"[ingest] Base ingest error: {e}")
    sample_root = Path(os.getenv("SAMPLE_DATA_DIR", "sample_data"))
    if parse_auth_logs:
        try:
            parse_auth_logs(sample_root)
            print("[ingest] Syslog .log ingested (recursive).")
        except Exception as e:
            print(f"[ingest] Syslog .log ingest error: {e}")
    else:
        print("[ingest] Syslog parser not available.")
    _ingest_csv_recursive(sample_root)
    return out_dir

if __name__ == "__main__":
    ingest_all()