import os
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_paths() -> Dict[str, str]:
    cfg = load_yaml(CONFIG_DIR / "paths.yaml")
    # Convert to absolute paths under project root
    resolved = {}
    for key, rel in cfg.items():
        resolved[key] = str((PROJECT_ROOT / rel).resolve())
    return resolved


def load_models_config() -> Dict[str, Any]:
    return load_yaml(CONFIG_DIR / "models.yaml")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_parquet_files(base_dir: Path) -> List[Path]:
    return list(base_dir.rglob("*.parquet"))


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
